"""Stable demonstration metrics; replace this source when OTRS tickets arrive."""
import hashlib
import random


class DemoProviderPerformanceSource:
    MONTHS = [(2026, month) for month in range(1, 11)]

    def get(self, provider_id, links, period="2026-10"):
        seed = int.from_bytes(hashlib.sha256(f"provider-{provider_id}-{period}".encode()).digest()[:8], "big")
        rng = random.Random(seed)
        tickets = max(1, round(links * rng.uniform(.06, .18)))
        missed_pct = rng.uniform(.025, .16)
        missed = min(tickets, round(tickets * missed_pct))
        met = tickets - missed
        recurrences = min(tickets, round(tickets * rng.uniform(.04, .22)))
        overdue = min(missed, round(missed * rng.uniform(.05, .55)))
        sla = met / tickets * 100
        uptime = round(rng.uniform(98.4, 99.99), 2)
        rating = round(rng.uniform(3.5, 4.95), 2)
        repeat_pct = recurrences / tickets * 100
        score = round(max(0, min(100, sla * .45 + rating / 5 * 25 + uptime * .2 + (100 - repeat_pct * 2) * .06 + (100 - missed_pct * 100) * .04)), 1)
        monthly = []
        for year, month in self.MONTHS:
            month_seed = int.from_bytes(hashlib.sha256(f"provider-{provider_id}-{year}-{month:02d}".encode()).digest()[:8], "big")
            monthly.append(max(1, round(links * random.Random(month_seed).uniform(.06, .18))))
        return {
            "chamados": tickets, "dentro_sla": met, "fora_sla": missed,
            "dentro_pct": round(sla, 1), "repeat_pct": round(repeat_pct, 1),
            "reincidencias": recurrences, "estourados": overdue,
            "uptime": uptime, "avaliacao": rating, "score": score,
            "history": monthly, "tendencia": rng.choice(["up", "down", "stable"]),
        }
