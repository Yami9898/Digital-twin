"""
app/model/grafcet.py
Machine à états GRAFCET du stérilisateur EtO.

GrafcetCycle orchestre les 3 couches (signals / physics / actuators) :
  - chaque step_fn récupère son ActuatorState via actuators_for_state()
  - délègue la physique générique (pression + thermique + vapeur) à step_physics()
  - conserve uniquement sa logique spécifique irremplaçable après step_physics
    (cinétique GT121, inject_steam_vapor, apply_gas_preexpo, apply_rinse_effects…)
  - stocke l'ActuatorState courant dans self.actuators à chaque pas

Les noms de Segment.name sont identiques à la version précédente.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.model.signals import (
    WATER_VAPOR_KEY,
    TOTAL_ETO_MASS_KG,
    PRECON_RH_EQ, PRECON_VAPOR_RELAX, PRECON_VAPOR_DRIFT,
    STEAM_TO_VAPOR_GAIN, DEC_STEAM_TO_VAPOR_GAIN,
    VAPOR_RELAX_DEC_STAB, VAPOR_RELAX_DEC_POSTVAC, VAPOR_RELAX_STAB,
    VAPOR_RELAX_GAS_STAB, VAPOR_RELAX_EXPO,
    VAPOR_RELAX_RINSE,
    EXPO_RH_EQ, EXPO_DRY_RH_EQ,
    RINSE_BREAK_RH_EQ, RINSE_VAC_RH_EQ,
    RINSE_BREAK_PUMP_FACTOR, RINSE_VAC_PUMP_FACTOR, FINAL_VAC_PUMP_FACTOR,
    GAS_CUMULATIVE_FACTOR,
    RATE_VACUUM_FROM_ATM, RATE_VACUUM_MID, RATE_VACUUM_LOW,
    RATE_N2_BREAK_SLOW, RATE_N2_RINSE, RATE_AIR_BREAK,
    RATE_ETO_INJECTION, RATE_N2_GAS, RATE_STEAM,
    DELTA_PT111, DELTA_PT112,
    effective_rate, pressure_avg, eto_p_from_mass, make_initial_state,
)
from app.model.physics import (
    step_physics,
    inject_steam_vapor,
    update_rh_from_vapor, finalize_state,
    preexpo_rh_eq, apply_gas_preexpo, apply_rinse_effects,
)
from app.model.actuators import (
    ActuatorState, CycleAlarm,
    actuators_for_state, safety_check,
)


class GrafcetCycle:
    """
    Machine à états GRAFCET du cycle de stérilisation EtO.

    Orchestre les couches signals / physics / actuators et produit la
    liste de Segment compatible avec les onglets de visualisation.

    États GRAFCET (19 états) dans l'ordre séquentiel :
        S0   Étape initiale
        S1   Préconditionnement          [conditionnel]
        S2   Vide initial
        S3   Test fuite bas
        S4   Test fuite haut             [conditionnel]
        S4a  Dilution azote ×NB220       [conditionnel]
        S4b  Conditionnement dynamique   [conditionnel]
        S5   Injection vapeur
        S6   Stabilisation humidité
        S8   Injection gaz ×4 (EtO / N2 alternés)
        S9   Exposition EtO
        S10  Vide avant rinçage
        S11  Rinçage azote ×NB620
        S12  Rinçage air ×NB680
        S12a Rinçage additionnel ×NB740  [conditionnel]
        S13  Casse vide finale
    """

    DT_INTERNAL = 0.5  # pas de simulation (minutes)

    CONDITIONAL_STATES = {
        "S1":   lambda r: float(r.get("Préconditionnement", {}).get(
                    "T130 - Durée préconditionnement", 0.0)) > 0,
        "S4":   lambda r: float(r.get("Test de fuite haut", {}).get(
                    "SP170 - Pression casse vide azote", 0.0)) > 0,
        "S4a":  lambda r: float(r.get("Dilution azote", {}).get(
                    "NB220 - Nombre dilution azote", 0.0)) > 0,
        "S4b":  lambda r: float(r.get("Conditionnement dynamique", {}).get(
                    "T250 - Durée conditionnement dynamique", 0.0)) > 0,
        "S12a": lambda r: float(r.get("Rinçage additionnel", {}).get(
                    "NB740 - Nombre de rinçages additionnels", 0.0)) > 0,
    }

    def __init__(self, recipe: Dict[str, Dict[str, float]]) -> None:
        self.recipe    = recipe
        self.signals   = make_initial_state(recipe)
        self.actuators = ActuatorState()
        self.segments: List = []
        self.jacket_sp = float(
            recipe.get("Général", {}).get("TS_JACKET - Consigne TT112", 49.0)
        )
        self._d111 = DELTA_PT111
        self._d112 = DELTA_PT112

    # ── Interface publique ────────────────────────────────────────────

    def simulate(self) -> Tuple[List, float]:
        """Simule le cycle complet. Retourne (segments, durée_totale_min)."""
        from app.model.sterilization_model import phase_is_active  # import tardif
        self._phase_is_active = phase_is_active
        self._run()
        total = sum(seg.duration for seg in self.segments)
        return self.segments, total

    def _state_is_active(self, state_id: str) -> bool:
        cond = self.CONDITIONAL_STATES.get(state_id)
        return cond is None or cond(self.recipe)

    # ── Cœur de la boucle de simulation ──────────────────────────────

    def _step_with_actuators(
        self,
        s: dict,
        dt: float,
        state_id: str,
        sub_state: str,
        phase_label: str,
        params: dict,
    ) -> dict:
        """Délègue la physique générique à step_physics via ActuatorState.

        Récupère l'ActuatorState via actuators_for_state(), le stocke dans
        self.actuators pour traçabilité IHM, puis appelle step_physics qui
        gère pression + thermique + vapeur + finalize.

        La logique spécifique (GT121, inject_steam_vapor, apply_gas_preexpo,
        apply_rinse_effects…) doit être appliquée APRÈS cet appel par le
        code appelant.
        """
        act = actuators_for_state(state_id, sub_state)
        self.actuators = act
        full_params = {
            "jacket_sp": self.jacket_sp,
            "d111": self._d111,
            "d112": self._d112,
            **params,
        }
        return step_physics(s, act, dt, full_params, phase_label)

    def _advance_phase(self, name: str, duration: float, step_fn) -> None:
        """Avance une phase pour *duration* minutes en pas de DT_INTERNAL."""
        from app.model.sterilization_model import Segment  # import tardif
        if duration <= 0:
            return
        remaining = float(duration)
        while remaining > 1e-9:
            dt      = min(self.DT_INTERNAL, remaining)
            elapsed = float(duration) - remaining
            start_s = dict(self.signals)
            next_s  = step_fn(dict(self.signals), dt, elapsed, float(duration))
            next_s  = update_rh_from_vapor(next_s)
            next_s  = finalize_state(next_s)
            self.segments.append(Segment(
                name=name,
                duration=max(0.01, dt),
                start_state=start_s,
                end_state=next_s,
            ))
            self.signals = next_s
            remaining -= dt

    # ── Orchestration principale ──────────────────────────────────────

    def _run(self) -> None:
        if self._state_is_active("S1"):
            self._run_S1_preconditionnement()
        self._run_S2_vide_initial()
        self._run_S3_test_fuite_bas()
        if self._state_is_active("S4"):
            self._run_S4_test_fuite_haut()
        if self._state_is_active("S4a"):
            self._run_S4a_dilution_azote()
        if self._state_is_active("S4b"):
            self._run_S4b_conditionnement_dynamique()
        self._run_S5_injection_vapeur()
        self._run_S6_stabilisation_humidite()
        self._run_S8_gas_injections()
        self._run_flush_azote()
        self._run_S9_exposition_eto()
        self._run_S10_vide_avant_rincage()
        self._run_S11_rincage_azote()
        self._run_S12_rincage_air()
        if self._state_is_active("S12a"):
            self._run_S12a_rincage_additionnel()
        self._run_S13_casse_vide_finale()

    # ── S1 — Préconditionnement ───────────────────────────────────────
    # Actionneurs : EH_jacket=1.0, CP_jacket, RC_recirc (aucune vanne pression)
    # → step_physics fait hold_pressure(p_before).

    def _run_S1_preconditionnement(self) -> None:
        data = self.recipe.get("Préconditionnement", {})
        t130 = float(data.get("T130 - Durée préconditionnement", 0.0))

        def step(s, dt, elapsed, total):
            s = self._step_with_actuators(s, dt, "S1", "", "Préconditionnement",
                params={
                    "vapor_rh":    PRECON_RH_EQ,
                    "vapor_k":     PRECON_VAPOR_RELAX,
                    "vapor_drift": -PRECON_VAPOR_DRIFT,  # négatif = accumulation
                })
            s["GT121"] = 0.0
            return s

        self._advance_phase("Préconditionnement", t130, step)

    # ── S2 — Vide initial ─────────────────────────────────────────────
    # Actionneurs : VP_vacuum + PV_vide → advance_pressure.
    # step_physics applique apply_vapor_pumping automatiquement (p baisse).

    def _run_S2_vide_initial(self) -> None:
        from app.model.sterilization_model import safe_duration_from_pressure
        data     = self.recipe["Vide initial"]
        target_p = data["SP140 - Consigne pression vide"]
        r140     = data["R140 - Vitesse de vide"]
        duration = safe_duration_from_pressure(
            target_p - pressure_avg(self.signals), r140, RATE_VACUUM_FROM_ATM)

        def step(s, dt, elapsed, total):
            s = self._step_with_actuators(s, dt, "S2", "", "Vide initial",
                params={
                    "target_p": target_p,
                    "rate":     r140,
                    "fallback": RATE_VACUUM_FROM_ATM,
                })
            s["GT121"] = 0.0
            return s

        self._advance_phase("Vide initial", duration, step)

    # ── S3 — Test de fuite bas ────────────────────────────────────────
    # Actionneurs : tous False → hold_pressure(p_before).
    # Logique spécifique : léger drift de pression (0.2 mbar/min) appliqué
    # après step_physics pour simuler la fuite.

    def _run_S3_test_fuite_bas(self) -> None:
        data     = self.recipe["Test de fuite bas"]
        target_p = pressure_avg(self.signals)
        duration = data["T160 - Durée"]

        def step(s, dt, elapsed, total):
            s = self._step_with_actuators(s, dt, "S3", "", "Test de fuite bas",
                params={})
            # Simulation de la fuite (0.2 mbar/min)
            leak_p = target_p + 0.2 * elapsed
            s["PT111"] = leak_p + self._d111
            s["PT112"] = leak_p + self._d112
            return s

        self._advance_phase("Test de fuite bas", duration, step)

    # ── S4 — Test de fuite haut ───────────────────────────────────────

    def _run_S4_test_fuite_haut(self) -> None:
        from app.model.sterilization_model import safe_duration_from_pressure
        data  = self.recipe["Test de fuite haut"]
        sp170 = data["SP170 - Pression casse vide azote"]
        r170  = data["R170 - Vitesse injection azote"]
        t190  = data["T190 - Durée test"]
        sp200 = data["SP200 - Consigne vide"]
        r200  = data["R200 - Vitesse de vide"]

        # Sous-phase injection N2
        dur_inj = safe_duration_from_pressure(
            sp170 - pressure_avg(self.signals), r170, RATE_N2_BREAK_SLOW)

        def step_inj(s, dt, elapsed, total):
            re   = effective_rate(r170, RATE_N2_BREAK_SLOW)
            dp   = min(re * dt, max(0.0, sp170 - pressure_avg(s)))
            s = self._step_with_actuators(s, dt, "S4", "injection",
                "Test fuite haut - injection azote",
                params={
                    "target_p": sp170,
                    "rate":     r170,
                    "fallback": RATE_N2_BREAK_SLOW,
                    "gas_drive": dp,
                })
            return s

        self._advance_phase("Test fuite haut - injection azote", dur_inj, step_inj)

        # Sous-phase test (maintien)
        def step_hold(s, dt, elapsed, total):
            s = self._step_with_actuators(s, dt, "S4", "hold",
                "Test fuite haut - test", params={})
            return s

        self._advance_phase("Test fuite haut - test", t190, step_hold)

        # Sous-phase vide
        dur_vac = safe_duration_from_pressure(
            sp200 - pressure_avg(self.signals), r200, RATE_VACUUM_MID)

        def step_vac(s, dt, elapsed, total):
            s = self._step_with_actuators(s, dt, "S4", "vide",
                "Test fuite haut - vide",
                params={
                    "target_p": sp200,
                    "rate":     r200,
                    "fallback": RATE_VACUUM_MID,
                })
            return s

        self._advance_phase("Test fuite haut - vide", dur_vac, step_vac)

    # ── S4a — Dilution azote ──────────────────────────────────────────

    def _run_S4a_dilution_azote(self) -> None:
        from app.model.sterilization_model import safe_duration_from_pressure
        data  = self.recipe["Dilution azote"]
        sp220 = data["SP220 - Pression dilution azote"]
        r220  = data["R220 - Vitesse injection dilution azote"]
        sp230 = data["SP230 - Consigne pression vide"]
        r230  = data["R230 - Vitesse du vide"]
        nb220 = max(1, int(round(data["NB220 - Nombre dilution azote"])))

        for i in range(nb220):
            dur_inj = safe_duration_from_pressure(
                sp220 - pressure_avg(self.signals), r220, RATE_N2_RINSE)

            def step_inj(s, dt, elapsed, total, _i=i):
                re = effective_rate(r220, RATE_N2_RINSE)
                dp = min(re * dt, max(0.0, sp220 - pressure_avg(s)))
                s = self._step_with_actuators(s, dt, "S4a", "injection",
                    f"Dilution azote {_i+1} - injection",
                    params={
                        "target_p": sp220,
                        "rate":     r220,
                        "fallback": RATE_N2_RINSE,
                        "gas_drive": dp,
                    })
                s["GT121"] *= max(0.0, 1.0 - 0.03 * dt)
                return s

            self._advance_phase(f"Dilution azote {i+1} - injection", dur_inj, step_inj)

            dur_vac = safe_duration_from_pressure(
                sp230 - pressure_avg(self.signals), r230, RATE_VACUUM_MID)

            def step_vac(s, dt, elapsed, total, _i=i):
                s = self._step_with_actuators(s, dt, "S4a", "vide",
                    f"Dilution azote {_i+1} - vide",
                    params={
                        "target_p": sp230,
                        "rate":     r230,
                        "fallback": RATE_VACUUM_MID,
                    })
                s["GT121"] *= max(0.0, 1.0 - 0.08 * dt)
                return s

            self._advance_phase(f"Dilution azote {i+1} - vide", dur_vac, step_vac)

    # ── S4b — Conditionnement dynamique (DEC) ────────────────────────

    def _run_S4b_conditionnement_dynamique(self) -> None:
        data   = self.recipe["Conditionnement dynamique"]
        t250   = data["T250 - Durée conditionnement dynamique"]
        p250   = int(round(data["P250 - Nombre de pulses"]))
        hr260  = data["HR260 - Humidité conditionnement"]
        pulses = max(1, p250) if p250 > 0 else max(1, int(max(1.0, t250) // 4))
        cyc_dt = max(self.DT_INTERNAL, t250 / (pulses * 4))

        for i in range(pulses):
            steam_step = 9.0

            def step_steam(s, dt, elapsed, total, _i=i):
                pb      = pressure_avg(s)
                rt      = pb + steam_step * (dt / max(total, 1e-6))
                re_loc  = steam_step / max(total, dt)
                dp_est  = min(re_loc * dt, max(0.0, rt - pb))
                s = self._step_with_actuators(s, dt, "S4b", "steam",
                    f"DEC {_i+1} - steam injection",
                    params={
                        "target_p":    rt,
                        "rate":        re_loc,
                        "fallback":    re_loc,
                        "steam_drive": dp_est,
                        "vapor_strength": 0.0,   # vapeur injectée manuellement
                    })
                # Injection vapeur condensée — appliquée après step_physics
                idp = max(0.0, pressure_avg(s) - pb)
                s = inject_steam_vapor(s, idp, DEC_STEAM_TO_VAPOR_GAIN)
                return s

            self._advance_phase(f"DEC {i+1} - steam injection", cyc_dt, step_steam)

            def step_stab(s, dt, elapsed, total, _i=i):
                s = self._step_with_actuators(s, dt, "S4b", "stabilisation",
                    f"DEC {_i+1} - stabilisation",
                    params={
                        "vapor_rh": hr260,
                        "vapor_k":  VAPOR_RELAX_DEC_STAB,
                    })
                return s

            self._advance_phase(f"DEC {i+1} - stabilisation", cyc_dt, step_stab)

            tgt_p = max(40.0, pressure_avg(self.signals) - 9.0)

            def step_vac(s, dt, elapsed, total, _i=i, _tp=tgt_p):
                s = self._step_with_actuators(s, dt, "S4b", "vide",
                    f"DEC {_i+1} - vacuum",
                    params={
                        "target_p": _tp,
                        "rate":     RATE_VACUUM_LOW,
                        "fallback": RATE_VACUUM_LOW,
                    })
                return s

            self._advance_phase(f"DEC {i+1} - vacuum", cyc_dt, step_vac)

            def step_post(s, dt, elapsed, total, _i=i):
                rh_tgt = min(hr260, preexpo_rh_eq("vacuum_after_stab", s))
                s = self._step_with_actuators(s, dt, "S4b", "stabilisation",
                    f"DEC {_i+1} - stabilisation après vide",
                    params={
                        "vapor_rh": rh_tgt,
                        "vapor_k":  VAPOR_RELAX_DEC_POSTVAC,
                    })
                return s

            self._advance_phase(f"DEC {i+1} - stabilisation après vide", cyc_dt, step_post)

    # ── S5 — Injection vapeur ─────────────────────────────────────────
    # Actionneur PV_steam=True → step_physics avance la pression.
    # vapor_strength=0 : pas de dilution (c'est de la vapeur qu'on injecte).
    # inject_steam_vapor() appliqué après pour ajouter P_H2O.

    def _run_S5_injection_vapeur(self) -> None:
        from app.model.sterilization_model import (
            safe_duration_from_pressure, phase_is_active,
        )
        data = self.recipe["Injection vapeur"]
        if not phase_is_active("Injection vapeur", data):
            return
        dp300     = data["DP300 - Pression injection vapeur"]
        r300      = data["R300 - Vitesse injection vapeur"]
        hr_target = data["HR300 - Consigne humidité"]
        target_p  = pressure_avg(self.signals) + dp300
        duration  = safe_duration_from_pressure(dp300, r300, RATE_STEAM)

        def step(s, dt, elapsed, total):
            pb      = pressure_avg(s)
            re      = effective_rate(r300, RATE_STEAM)
            dp_est  = min(re * dt, max(0.0, target_p - pb))
            params  = {
                "target_p":       target_p,
                "rate":           r300,
                "fallback":       RATE_STEAM,
                "steam_drive":    dp_est,
                "vapor_strength": 0.0,  # vapeur injectée via inject_steam_vapor
            }
            if hr_target > 0:
                params["vapor_rh"] = hr_target
                params["vapor_k"]  = VAPOR_RELAX_STAB * 0.35
            s = self._step_with_actuators(s, dt, "S5", "", "Injection vapeur", params)
            # Ajout de P_H2O proportionnel à la vapeur effectivement injectée
            idp = max(0.0, pressure_avg(s) - pb)
            s = inject_steam_vapor(s, idp, STEAM_TO_VAPOR_GAIN)
            return s

        self._advance_phase("Injection vapeur", duration, step)

    # ── S6 — Stabilisation humidité ───────────────────────────────────
    # Pression descend lentement. vapor_strength=0 : on ne pompe pas la vapeur,
    # l'humidité est maintenue par relaxation vers preexpo_rh_eq.

    def _run_S6_stabilisation_humidite(self) -> None:
        from app.model.sterilization_model import phase_is_active
        data = self.recipe["Stabilisation humidité"]
        if not phase_is_active("Stabilisation humidité", data):
            return
        t310    = data["T310 - Temps stabilisation"]
        sp320   = data["SP320 - Consigne de vide"]
        r320    = data["R320 - Vitesse de vide"]
        start_p = pressure_avg(self.signals)

        def lerp_local(a, b, u):
            return a + (b - a) * u

        def step(s, dt, elapsed, total):
            tgt      = lerp_local(start_p, sp320, (elapsed + dt) / max(total, dt))
            rh_eq    = preexpo_rh_eq("stabilisation", s)
            s = self._step_with_actuators(s, dt, "S6", "", "Stabilisation humidité",
                params={
                    "target_p":       tgt,
                    "rate":           r320,
                    "fallback":       RATE_VACUUM_LOW,
                    "vapor_strength": 0.0,   # humidité maintenue, pas pompée
                    "vapor_rh":       rh_eq,
                    "vapor_k":        VAPOR_RELAX_STAB,
                    "vapor_drift":    0.01,
                })
            return s

        self._advance_phase("Stabilisation humidité", t310, step)

    # ── S8 — Injections gaz EtO / N2 (×4) ───────────────────────────
    # EtO (gi 0, 2) : PV_EtO=True; N2 (gi 1, 3) : PV_N2=True.
    # Pression dérivée de la masse EtO (lerp + eto_p_from_mass) — override
    # de PT111/PT112 après step_physics.

    def _run_S8_gas_injections(self) -> None:
        from app.model.sterilization_model import (
            safe_duration_from_pressure, phase_is_active,
        )
        gas_specs = [
            ("Injection gaz 1", "DP330 - Injection gaz 1",
             "R330 - Vitesse injection gaz 1", "T350 - Stabilisation gaz 1", 0.22),
            ("Injection gaz 2", "DP390 - Injection gaz 2",
             "R390 - Vitesse injection gaz 2", "T410 - Stabilisation gaz 2", 0.28),
            ("Injection gaz 3", "DP450 - Injection gaz 3",
             "R450 - Vitesse injection gaz 3", "T470 - Stabilisation gaz 3", 0.30),
            ("Injection gaz 4", "DP510 - Injection gaz 4",
             "R510 - Vitesse injection gaz 4", "T530 - Stabilisation gaz 4", 0.20),
        ]
        afs = sum(mf for pn, _, _, _, mf in gas_specs
                  if phase_is_active(pn, self.recipe[pn]))
        ETO_INDICES = {0, 2}

        for gi, (pname, dp_key, r_key, t_key, mf) in enumerate(gas_specs):
            data = self.recipe[pname]
            if not phase_is_active(pname, data):
                continue

            dp     = data[dp_key]
            r      = data[r_key]
            t_stab = data[t_key]
            gf     = 1.0 + gi * GAS_CUMULATIVE_FACTOR
            cur_m  = max(0.0, self.signals["GT121"])
            nf     = mf / afs if afs > 0 else 0.0
            tgt_m  = min(TOTAL_ETO_MASS_KG, cur_m + TOTAL_ETO_MASS_KG * nf)
            tgt_p  = max(pressure_avg(self.signals) + dp,
                         eto_p_from_mass(tgt_m, self.signals["TT111"]))
            rate_fb = RATE_ETO_INJECTION if gi in ETO_INDICES else RATE_N2_GAS
            duration = safe_duration_from_pressure(
                tgt_p - pressure_avg(self.signals), r, rate_fb)
            state_p0 = pressure_avg(self.signals)
            sub_inj  = "eto_injection" if gi in ETO_INDICES else "n2_injection"

            def step_inj(s, dt, elapsed, total,
                         _pn=pname, _cm=cur_m, _tm=tgt_m, _tp=tgt_p,
                         _sp0=state_p0, _gf=gf, _rf=rate_fb, _sub=sub_inj, _r=r):
                prog     = min(1.0, max(0.0, (elapsed + dt) / max(total, dt)))
                gt121_new = _cm + (_tm - _cm) * ((elapsed + dt) / max(total, dt))
                ep       = eto_p_from_mass(gt121_new, s["TT111"])
                cp       = _sp0 + (_tp - _sp0) * ((elapsed + dt) / max(total, dt))
                rp       = max(cp, ep)
                pb       = pressure_avg(s)
                dp_est   = max(0.0, rp - pb)
                s = self._step_with_actuators(s, dt, "S8", _sub,
                    f"{_pn} - injection",
                    params={
                        "target_p":  rp,
                        "rate":      _r,
                        "fallback":  _rf,
                        "gas_drive": _gf * dp_est,
                    })
                # Logique spécifique : masse EtO + pression exacte
                s["GT121"] = gt121_new
                s["PT111"] = rp + self._d111
                s["PT112"] = rp + self._d112
                s = apply_gas_preexpo(s, dt, prog, _gf)
                return s

            self._advance_phase(f"{pname} - injection", duration, step_inj)

            hold_p = max(eto_p_from_mass(tgt_m, self.signals["TT111"]),
                         pressure_avg(self.signals) * 0.995)

            def step_stab(s, dt, elapsed, total,
                          _pn=pname, _tm=tgt_m, _hp=hold_p, _gf=gf):
                rh_eq = preexpo_rh_eq("gas_stabilisation", s, _gf)
                s = self._step_with_actuators(s, dt, "S8", "",
                    f"{_pn} - stabilisation",
                    params={
                        "vapor_rh":    rh_eq,
                        "vapor_k":     VAPOR_RELAX_GAS_STAB,
                        "vapor_drift": 0.02,
                    })
                s["GT121"] = _tm
                s["PT111"] = _hp + self._d111
                s["PT112"] = _hp + self._d112
                return s

            self._advance_phase(f"{pname} - stabilisation",
                                max(self.DT_INTERNAL, t_stab), step_stab)

    # ── Flush azote (entre S8 et S9) ──────────────────────────────────

    def _run_flush_azote(self) -> None:
        from app.model.sterilization_model import (
            safe_duration_from_pressure, phase_is_active,
        )
        data = self.recipe["Flush azote"]
        if not phase_is_active("Flush azote", data):
            return
        dp570     = data["DP570 - Injection azote"]
        r570      = data["R570 - Vitesse injection azote"]
        tgt_p     = pressure_avg(self.signals) + dp570
        duration  = safe_duration_from_pressure(dp570, r570, RATE_N2_GAS)
        init_mass = self.signals["GT121"]

        def step(s, dt, elapsed, total):
            re    = effective_rate(r570, RATE_N2_GAS)
            dp_e  = min(re * dt, max(0.0, tgt_p - pressure_avg(s)))
            s = self._step_with_actuators(s, dt, "S8", "n2_injection", "Flush azote",
                params={
                    "target_p":  tgt_p,
                    "rate":      r570,
                    "fallback":  RATE_N2_GAS,
                    "gas_drive": dp_e,
                })
            s["GT121"] = max(0.0, init_mass * (1.0 - 0.65 * ((elapsed + dt) / max(total, dt))))
            return s

        self._advance_phase("Flush azote", duration, step)

    # ── S9 — Exposition EtO ───────────────────────────────────────────
    # Actionneurs : RC_recirc + EH_jacket (aucune vanne pression).
    # step_physics fait hold_pressure(p_before).

    def _run_S9_exposition_eto(self) -> None:
        from app.model.sterilization_model import phase_is_active
        data = self.recipe["Exposition EtO"]
        if not phase_is_active("Exposition EtO", data):
            return
        t580   = data["T580 - Temps exposition"]
        ec580  = data["EC580 - Concentration cible"]
        tgt_p  = max(pressure_avg(self.signals),
                     eto_p_from_mass(self.signals["GT121"], self.signals["TT111"]))
        expo_rh = (EXPO_RH_EQ
                   if phase_is_active("Conditionnement dynamique",
                                      self.recipe["Conditionnement dynamique"])
                   else EXPO_DRY_RH_EQ)

        ok, reason = safety_check("S9", self.signals)
        if not ok:
            raise CycleAlarm(f"S9 Exposition EtO bloquée : {reason}", level=2)

        def step(s, dt, elapsed, total):
            s = self._step_with_actuators(s, dt, "S9", "", "Exposition EtO",
                params={
                    "target_p": tgt_p,
                    "vapor_rh": expo_rh,
                    "vapor_k":  VAPOR_RELAX_EXPO,
                })
            if ec580 > 0:
                s["GT121"] += 0.05 * (min(TOTAL_ETO_MASS_KG, ec580 / 100.0)
                                       - s["GT121"]) * dt
            return s

        self._advance_phase("Exposition EtO", t580, step)

    # ── S10 — Vide avant rinçage ──────────────────────────────────────

    def _run_S10_vide_avant_rincage(self) -> None:
        from app.model.sterilization_model import (
            safe_duration_from_pressure, phase_is_active,
        )
        data = self.recipe["Vide avant rinçage"]
        if not phase_is_active("Vide avant rinçage", data):
            return
        sp590     = data["SP590 - Consigne vide"]
        r590      = data["R590 - Vitesse de vide"]
        duration  = safe_duration_from_pressure(
            sp590 - pressure_avg(self.signals), r590, RATE_VACUUM_MID)
        init_mass = self.signals["GT121"]

        def step(s, dt, elapsed, total):
            s = self._step_with_actuators(s, dt, "S10", "", "Vide avant rinçage",
                params={
                    "target_p":       sp590,
                    "rate":           r590,
                    "fallback":       RATE_VACUUM_MID,
                    "vapor_strength": FINAL_VAC_PUMP_FACTOR,
                })
            s["GT121"] = max(0.0, init_mass * (1.0 - 0.85 * ((elapsed + dt) / max(total, dt))))
            return s

        self._advance_phase("Vide avant rinçage", duration, step)

    # ── S11 — Rinçage azote ×NB620 ────────────────────────────────────

    def _run_S11_rincage_azote(self) -> None:
        from app.model.sterilization_model import (
            safe_duration_from_pressure, phase_is_active,
        )
        az = self.recipe["Rinçage azote"]
        if not phase_is_active("Rinçage azote", az):
            return
        sp620 = az["SP620 - Pression casse vide azote"]
        r620  = az["R620 - Vitesse casse vide azote"]
        t630  = az["T630 - Stabilisation casse vide"]
        sp640 = az["SP640 - Consigne vide"]
        r640  = az["R640 - Vitesse de vide"]
        t660  = az["T660 - Stabilisation vide"]
        nb620 = max(0, int(round(az["NB620 - Nombre de rinçages azote"])))

        for i in range(nb620):
            mbc     = self.signals["GT121"]
            dur_inj = safe_duration_from_pressure(
                sp620 - pressure_avg(self.signals), r620, RATE_N2_RINSE)

            def step_inj(s, dt, elapsed, total, _i=i, _mbc=mbc):
                re   = effective_rate(r620, RATE_N2_RINSE)
                dp_e = min(re * dt, max(0.0, sp620 - pressure_avg(s)))
                s = self._step_with_actuators(s, dt, "S11", "injection",
                    f"Rinçage azote {_i+1} - injection azote",
                    params={
                        "target_p":  sp620,
                        "rate":      r620,
                        "fallback":  RATE_N2_RINSE,
                        "gas_drive": dp_e,
                    })
                s["GT121"] = max(0.0, _mbc * (1.0 - 0.35 * ((elapsed + dt) / max(total, dt))))
                s = apply_rinse_effects(s, dt, elapsed, _i,
                                        RINSE_BREAK_RH_EQ, RINSE_BREAK_PUMP_FACTOR, 0.8)
                return s

            self._advance_phase(f"Rinçage azote {i+1} - injection azote", dur_inj, step_inj)

            def step_hold(s, dt, elapsed, total, _i=i):
                s = self._step_with_actuators(s, dt, "S11", "stabilisation",
                    f"Rinçage azote {_i+1} - stabilisation injection",
                    params={
                        "vapor_rh": 24.0,
                        "vapor_k":  VAPOR_RELAX_RINSE * 0.7,
                    })
                s["GT121"] *= max(0.0, 1.0 - 0.05 * dt)
                return s

            self._advance_phase(f"Rinçage azote {i+1} - stabilisation injection",
                                max(self.DT_INTERNAL, t630), step_hold)

            mbv     = self.signals["GT121"]
            dur_vac = safe_duration_from_pressure(
                sp640 - pressure_avg(self.signals), r640, RATE_VACUUM_MID)

            def step_vac(s, dt, elapsed, total, _i=i, _mbv=mbv):
                s = self._step_with_actuators(s, dt, "S11", "vide",
                    f"Rinçage azote {_i+1} - vide",
                    params={
                        "target_p":       sp640,
                        "rate":           r640,
                        "fallback":       RATE_VACUUM_MID,
                        "vapor_strength": 0.5,
                    })
                s["GT121"] = max(0.0, _mbv * (1.0 - 0.55 * ((elapsed + dt) / max(total, dt))))
                s = apply_rinse_effects(s, dt, elapsed + 1.3, _i,
                                        RINSE_VAC_RH_EQ, RINSE_VAC_PUMP_FACTOR, 1.0)
                return s

            self._advance_phase(f"Rinçage azote {i+1} - vide", dur_vac, step_vac)

            def step_stab(s, dt, elapsed, total, _i=i):
                s = self._step_with_actuators(s, dt, "S11", "stabilisation",
                    f"Rinçage azote {_i+1} - stabilisation vide",
                    params={
                        "vapor_rh": 18.0,
                        "vapor_k":  VAPOR_RELAX_RINSE * 0.6,
                    })
                s["GT121"] *= max(0.0, 1.0 - 0.02 * dt)
                return s

            self._advance_phase(f"Rinçage azote {i+1} - stabilisation vide",
                                max(self.DT_INTERNAL, t660), step_stab)

    # ── S12 — Rinçage air ×NB680 ──────────────────────────────────────

    def _run_S12_rincage_air(self) -> None:
        from app.model.sterilization_model import (
            safe_duration_from_pressure, phase_is_active,
        )
        air = self.recipe["Rinçage air"]
        if not phase_is_active("Rinçage air", air):
            return
        sp680 = air["SP680 - Pression casse vide air"]
        r680  = air["R680 - Vitesse casse vide air"]
        t690  = air["T690 - Stabilisation casse vide"]
        sp700 = air["SP700 - Consigne vide"]
        r700  = air["R700 - Vitesse de vide"]
        t720  = air["T720 - Stabilisation vide"]
        nb680 = max(0, int(round(air["NB680 - Nombre de rinçages air"])))

        for i in range(nb680):
            dur_break = safe_duration_from_pressure(
                sp680 - pressure_avg(self.signals), r680, RATE_AIR_BREAK)

            def step_break(s, dt, elapsed, total, _i=i):
                re   = effective_rate(r680, RATE_AIR_BREAK)
                dp_e = min(re * dt, max(0.0, sp680 - pressure_avg(s)))
                s = self._step_with_actuators(s, dt, "S12", "break",
                    f"Rinçage air {_i+1} - casse vide air",
                    params={
                        "target_p":  sp680,
                        "rate":      r680,
                        "fallback":  RATE_AIR_BREAK,
                        "gas_drive": dp_e,
                    })
                s["GT121"] *= max(0.0, 1.0 - 0.12 * dt)
                s = apply_rinse_effects(s, dt, elapsed + 0.4, _i, 26.0,
                                        RINSE_BREAK_PUMP_FACTOR * 0.8, 0.6)
                return s

            self._advance_phase(f"Rinçage air {i+1} - casse vide air", dur_break, step_break)

            def step_stab_break(s, dt, elapsed, total, _i=i):
                s = self._step_with_actuators(s, dt, "S12", "stabilisation",
                    f"Rinçage air {_i+1} - stabilisation casse vide",
                    params={
                        "vapor_rh": 24.0,
                        "vapor_k":  VAPOR_RELAX_RINSE * 0.75,
                    })
                s["GT121"] *= max(0.0, 1.0 - 0.05 * dt)
                return s

            self._advance_phase(f"Rinçage air {i+1} - stabilisation casse vide",
                                max(self.DT_INTERNAL, t690), step_stab_break)

            dur_vac = safe_duration_from_pressure(
                sp700 - pressure_avg(self.signals), r700, RATE_VACUUM_MID)

            def step_vac(s, dt, elapsed, total, _i=i):
                s = self._step_with_actuators(s, dt, "S12", "vide",
                    f"Rinçage air {_i+1} - vide",
                    params={
                        "target_p":       sp700,
                        "rate":           r700,
                        "fallback":       RATE_VACUUM_MID,
                        "vapor_strength": 0.5,
                    })
                s["GT121"] *= max(0.0, 1.0 - 0.16 * dt)
                s = apply_rinse_effects(s, dt, elapsed + 1.7, _i, 15.0,
                                        RINSE_VAC_PUMP_FACTOR * 0.9, 0.9)
                return s

            self._advance_phase(f"Rinçage air {i+1} - vide", dur_vac, step_vac)

            def step_stab_vac(s, dt, elapsed, total, _i=i):
                s = self._step_with_actuators(s, dt, "S12", "stabilisation",
                    f"Rinçage air {_i+1} - stabilisation vide",
                    params={
                        "vapor_rh": 16.0,
                        "vapor_k":  VAPOR_RELAX_RINSE * 0.55,
                    })
                return s

            self._advance_phase(f"Rinçage air {i+1} - stabilisation vide",
                                max(self.DT_INTERNAL, t720), step_stab_vac)

    # ── S12a — Rinçage additionnel ×NB740 ────────────────────────────

    def _run_S12a_rincage_additionnel(self) -> None:
        from app.model.sterilization_model import (
            safe_duration_from_pressure, phase_is_active,
        )
        add = self.recipe["Rinçage additionnel"]
        if not phase_is_active("Rinçage additionnel", add):
            return
        sp740 = add["SP740 - Pression casse vide air"]
        r740  = add["R740 - Vitesse casse vide air"]
        t750  = add["T750 - Stabilisation casse vide"]
        sp760 = add["SP760 - Consigne vide"]
        r760  = add["R760 - Vitesse de vide"]
        t780  = add["T780 - Stabilisation vide"]
        nb740 = max(1, int(round(add["NB740 - Nombre de rinçages additionnels"])))

        for i in range(nb740):
            bt = sp740 if sp740 > 0 else 200.0
            vt = sp760 if sp760 > 0 else 20.0
            dur_break = safe_duration_from_pressure(
                bt - pressure_avg(self.signals), r740, RATE_AIR_BREAK)

            def step_break(s, dt, elapsed, total, _i=i, _bt=bt):
                re   = effective_rate(r740, RATE_AIR_BREAK)
                dp_e = min(re * dt, max(0.0, _bt - pressure_avg(s)))
                s = self._step_with_actuators(s, dt, "S12a", "break",
                    f"Rinçage additionnel {_i+1} - air vacuum break",
                    params={
                        "target_p":  _bt,
                        "rate":      r740,
                        "fallback":  RATE_AIR_BREAK,
                        "gas_drive": dp_e,
                    })
                s = apply_rinse_effects(s, dt, elapsed + 0.8, _i, 20.0,
                                        RINSE_BREAK_PUMP_FACTOR * 0.7, 0.5)
                return s

            self._advance_phase(f"Rinçage additionnel {i+1} - air vacuum break",
                                dur_break, step_break)

            def step_hb(s, dt, elapsed, total, _i=i, _bt=bt):
                s = self._step_with_actuators(s, dt, "S12a", "stabilisation",
                    f"Rinçage additionnel {_i+1} - stabilisation casse vide",
                    params={
                        "vapor_rh": 20.0,
                        "vapor_k":  VAPOR_RELAX_RINSE * 0.7,
                    })
                return s

            self._advance_phase(f"Rinçage additionnel {i+1} - stabilisation casse vide",
                                max(self.DT_INTERNAL, t750), step_hb)

            dur_vac = safe_duration_from_pressure(
                vt - pressure_avg(self.signals), r760, RATE_VACUUM_MID)

            def step_vac(s, dt, elapsed, total, _i=i, _vt=vt):
                s = self._step_with_actuators(s, dt, "S12a", "vide",
                    f"Rinçage additionnel {_i+1} - vacuum",
                    params={
                        "target_p":       _vt,
                        "rate":           r760,
                        "fallback":       RATE_VACUUM_MID,
                        "vapor_strength": 0.5,
                    })
                s = apply_rinse_effects(s, dt, elapsed + 2.1, _i, 12.0,
                                        RINSE_VAC_PUMP_FACTOR, 0.8)
                return s

            self._advance_phase(f"Rinçage additionnel {i+1} - vacuum", dur_vac, step_vac)

            def step_hv(s, dt, elapsed, total, _i=i, _vt=vt):
                s = self._step_with_actuators(s, dt, "S12a", "stabilisation",
                    f"Rinçage additionnel {_i+1} - stabilisation vide",
                    params={
                        "vapor_rh": 12.0,
                        "vapor_k":  VAPOR_RELAX_RINSE * 0.5,
                    })
                return s

            self._advance_phase(f"Rinçage additionnel {i+1} - stabilisation vide",
                                max(self.DT_INTERNAL, t780), step_hv)

    # ── S13 — Casse vide air finale ───────────────────────────────────

    def _run_S13_casse_vide_finale(self) -> None:
        from app.model.sterilization_model import (
            safe_duration_from_pressure, phase_is_active,
        )
        data = self.recipe["Casse vide air finale"]
        if not phase_is_active("Casse vide air finale", data):
            return
        sp790    = data["SP790 - Consigne finale"]
        r790     = data["R790 - Vitesse finale"]
        duration = safe_duration_from_pressure(
            sp790 - pressure_avg(self.signals), r790, RATE_AIR_BREAK)

        def step(s, dt, elapsed, total):
            re   = effective_rate(r790, RATE_AIR_BREAK)
            dp_e = min(re * dt, max(0.0, sp790 - pressure_avg(s)))
            s = self._step_with_actuators(s, dt, "S13", "", "Casse vide air finale",
                params={
                    "target_p":  sp790,
                    "rate":      r790,
                    "fallback":  RATE_AIR_BREAK,
                    "gas_drive": dp_e,
                })
            s["GT121"] = max(0.0, s["GT121"] * (1.0 - 0.2 * dt))
            return s

        self._advance_phase("Casse vide air finale", duration, step)
