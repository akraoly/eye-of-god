"""
OSINT & Threat Actor Intelligence Engine.
15 groupes APT, enrichissement IOC, investigations.
Portage depuis AEGIS AI v3.1.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database.models import OsintActor, OsintInvestigation, ThreatIOC
import logging

log = logging.getLogger("SOC.OSINT")

# ── Base APT ──────────────────────────────────────────────────────────────────
SEED_ACTORS = [
    {"name": "APT28 — Fancy Bear",
     "aliases": ["Sofacy","Pawn Storm","STRONTIUM","Tsar Team"],
     "country": "Russie", "sponsor": "STATE",
     "motivation": ["ESPIONAGE","DISRUPTION"], "threat_level": "CRITICAL",
     "sophistication": "ADVANCED", "active_since": "2004", "is_active": True,
     "target_sectors": ["Government","Defense","Energy","Media","Elections"],
     "target_countries": ["USA","Germany","France","Ukraine","Georgia"],
     "primary_ttps": ["T1566.001","T1078","T1027","T1055","T1190"],
     "description": "GRU Unit 26165. Responsable SolarWinds, DNC hack, campagnes électorales 2016-2024."},

    {"name": "APT29 — Cozy Bear",
     "aliases": ["The Dukes","NOBELIUM","Midnight Blizzard"],
     "country": "Russie", "sponsor": "STATE",
     "motivation": ["ESPIONAGE"], "threat_level": "CRITICAL",
     "sophistication": "ADVANCED", "active_since": "2008", "is_active": True,
     "target_sectors": ["Government","Diplomatic","Think Tanks","Healthcare"],
     "target_countries": ["USA","UK","Europe","Ukraine"],
     "primary_ttps": ["T1566","T1078","T1105","T1027","T1070","T1021"],
     "description": "SVR russe. SolarWinds supply chain, Microsoft Exchange breach 2024, COVID vaccine espionage."},

    {"name": "APT41 — Double Dragon",
     "aliases": ["Winnti","Barium","Wicked Panda"],
     "country": "Chine", "sponsor": "STATE",
     "motivation": ["ESPIONAGE","FINANCIAL"], "threat_level": "CRITICAL",
     "sophistication": "ADVANCED", "active_since": "2012", "is_active": True,
     "target_sectors": ["Healthcare","Telecom","Finance","Gaming","Technology"],
     "target_countries": ["USA","Japan","India","Australia","UK"],
     "primary_ttps": ["T1566.001","T1190","T1059","T1078","T1055","T1486"],
     "description": "Double mandat : espionnage étatique ET cybercriminalité financière. Supply chain attacks."},

    {"name": "Lazarus Group",
     "aliases": ["HIDDEN COBRA","Zinc","APT38"],
     "country": "Corée du Nord", "sponsor": "STATE",
     "motivation": ["FINANCIAL","ESPIONAGE","DISRUPTION"], "threat_level": "CRITICAL",
     "sophistication": "ADVANCED", "active_since": "2009", "is_active": True,
     "target_sectors": ["Financial","Cryptocurrency","Defense","Media"],
     "target_countries": ["USA","South Korea","Japan","Europe"],
     "primary_ttps": ["T1566","T1059","T1055","T1486","T1041","T1190"],
     "description": "DPRK. WannaCry, Sony Pictures, Bangladesh Bank heist $81M, crypto thefts $2B+."},

    {"name": "APT1 — Comment Crew",
     "aliases": ["Comment Panda","Unit 61398"],
     "country": "Chine", "sponsor": "STATE",
     "motivation": ["ESPIONAGE"], "threat_level": "HIGH",
     "sophistication": "INTERMEDIATE", "active_since": "2006", "is_active": False,
     "target_sectors": ["Aerospace","Defense","IT","Energy","Finance"],
     "target_countries": ["USA","UK","Canada","Australia"],
     "primary_ttps": ["T1566.001","T1059","T1021","T1083","T1041"],
     "description": "PLA Unit 61398. Opération massive d'espionnage industriel US 2006-2013."},

    {"name": "Sandworm",
     "aliases": ["Voodoo Bear","BlackEnergy","TeleBots"],
     "country": "Russie", "sponsor": "STATE",
     "motivation": ["DISRUPTION","SABOTAGE"], "threat_level": "CRITICAL",
     "sophistication": "ADVANCED", "active_since": "2009", "is_active": True,
     "target_sectors": ["Energy","Government","Media","Financial"],
     "target_countries": ["Ukraine","USA","Europe"],
     "primary_ttps": ["T1190","T1059","T1486","T1490","T1078","T1562"],
     "description": "GRU Unit 74455. NotPetya ($10B), BlackEnergy Ukraine power grid 2015-2016."},

    {"name": "FIN7",
     "aliases": ["Carbanak","Navigator Group","Sangria Tempest"],
     "country": "Ukraine/Russie", "sponsor": "CRIMINAL",
     "motivation": ["FINANCIAL"], "threat_level": "HIGH",
     "sophistication": "ADVANCED", "active_since": "2015", "is_active": True,
     "target_sectors": ["Retail","Hospitality","Finance","Restaurant"],
     "target_countries": ["USA","Europe","Australia"],
     "primary_ttps": ["T1566.001","T1059.001","T1055","T1041","T1486"],
     "description": "Crime organisé. POS malware, vol de cartes. Revenu estimé : $1B+."},

    {"name": "Conti",
     "aliases": ["Wizard Spider","UNC1878"],
     "country": "Russie", "sponsor": "CRIMINAL",
     "motivation": ["FINANCIAL"], "threat_level": "CRITICAL",
     "sophistication": "ADVANCED", "active_since": "2020", "is_active": False,
     "target_sectors": ["Healthcare","Government","Finance"],
     "target_countries": ["USA","UK","Germany","France"],
     "primary_ttps": ["T1566","T1078","T1021","T1486","T1490"],
     "description": "RaaS fermé en 2022 après fuite de 60K messages internes. Ciblage soins de santé COVID."},

    {"name": "Scattered Spider",
     "aliases": ["0ktapus","Starfraud","UNC3944"],
     "country": "USA/UK", "sponsor": "CRIMINAL",
     "motivation": ["FINANCIAL"], "threat_level": "HIGH",
     "sophistication": "INTERMEDIATE", "active_since": "2022", "is_active": True,
     "target_sectors": ["Technology","Telecom","Gaming","Crypto","Finance"],
     "target_countries": ["USA","UK","Canada"],
     "primary_ttps": ["T1566","T1078","T1621","T1556","T1648"],
     "description": "Jeunes anglophones (16-22 ans). Social engineering avancé, SIM swapping, MGM Resorts $100M."},

    {"name": "REvil / Sodinokibi",
     "aliases": ["GandCrab","Unknown"],
     "country": "Russie", "sponsor": "CRIMINAL",
     "motivation": ["FINANCIAL"], "threat_level": "CRITICAL",
     "sophistication": "ADVANCED", "active_since": "2019", "is_active": False,
     "target_sectors": ["Manufacturing","Legal","Finance","Healthcare"],
     "target_countries": ["USA","Europe","Australia"],
     "primary_ttps": ["T1190","T1486","T1490","T1041"],
     "description": "RaaS. Kaseya VSA supply chain, JBS $11M, Acer $50M. Démantelé par FSB en 2022."},

    {"name": "Kimsuky",
     "aliases": ["Thallium","APT43","Velvet Chollima"],
     "country": "Corée du Nord", "sponsor": "STATE",
     "motivation": ["ESPIONAGE","FINANCIAL"], "threat_level": "HIGH",
     "sophistication": "INTERMEDIATE", "active_since": "2012", "is_active": True,
     "target_sectors": ["Government","Think Tanks","Nuclear","Crypto"],
     "target_countries": ["South Korea","USA","Japan","Europe"],
     "primary_ttps": ["T1566","T1059","T1583","T1078","T1041"],
     "description": "DPRK. Espionnage nucléaire, think tanks, phishing ciblé chercheurs."},

    {"name": "TA505",
     "aliases": ["Evil Corp","Dridex Group"],
     "country": "Russie", "sponsor": "CRIMINAL",
     "motivation": ["FINANCIAL"], "threat_level": "HIGH",
     "sophistication": "ADVANCED", "active_since": "2014", "is_active": True,
     "target_sectors": ["Financial","Retail","Healthcare"],
     "target_countries": ["USA","UK","Europe"],
     "primary_ttps": ["T1566.001","T1059","T1055","T1041","T1486"],
     "description": "Cl0p ransomware, Dridex banking trojan, FlawedAmmyy RAT."},

    {"name": "Charming Kitten",
     "aliases": ["APT35","Magic Hound","Mint Sandstorm"],
     "country": "Iran", "sponsor": "STATE",
     "motivation": ["ESPIONAGE"], "threat_level": "HIGH",
     "sophistication": "INTERMEDIATE", "active_since": "2014", "is_active": True,
     "target_sectors": ["Government","Academic","Media","Activiste"],
     "target_countries": ["USA","Israel","UK","Iran (dissidents)"],
     "primary_ttps": ["T1566","T1078","T1189","T1539","T1598"],
     "description": "IRGC. Hameçonnage chercheurs, journalistes, activistes iraniens."},

    {"name": "MuddyWater",
     "aliases": ["SeedWorm","TEMP.Zagros","Static Kitten"],
     "country": "Iran", "sponsor": "STATE",
     "motivation": ["ESPIONAGE","DISRUPTION"], "threat_level": "HIGH",
     "sophistication": "INTERMEDIATE", "active_since": "2017", "is_active": True,
     "target_sectors": ["Telecom","Government","Defense","Oil&Gas"],
     "target_countries": ["Middle East","Europe","USA"],
     "primary_ttps": ["T1566.001","T1059.001","T1021","T1078","T1562"],
     "description": "MOIS iranien. Spear-phishing, RATs personnalisés, ciblage géopolitique Moyen-Orient."},

    {"name": "SilverFish",
     "aliases": ["UNC2628","DEV-0537"],
     "country": "Inconnu", "sponsor": "CRIMINAL",
     "motivation": ["FINANCIAL","ESPIONAGE"], "threat_level": "HIGH",
     "sophistication": "ADVANCED", "active_since": "2020", "is_active": True,
     "target_sectors": ["Technology","Government","Finance"],
     "target_countries": ["USA","Europe"],
     "primary_ttps": ["T1078","T1621","T1566","T1648","T1548"],
     "description": "Groupe de type Lapsus$. Social engineering, insider threats, extorsion."},
]


class OsintEngine:

    def init_actors(self, db: Session) -> int:
        existing = db.query(OsintActor).count()
        if existing > 0:
            return existing
        for a in SEED_ACTORS:
            actor = OsintActor(
                name=a["name"],
                aliases=json.dumps(a.get("aliases", [])),
                country=a.get("country"),
                sponsor=a.get("sponsor"),
                motivation=json.dumps(a.get("motivation", [])),
                threat_level=a.get("threat_level", "MEDIUM"),
                sophistication=a.get("sophistication", "INTERMEDIATE"),
                is_active=a.get("is_active", True),
                active_since=a.get("active_since"),
                target_sectors=json.dumps(a.get("target_sectors", [])),
                target_countries=json.dumps(a.get("target_countries", [])),
                primary_ttps=json.dumps(a.get("primary_ttps", [])),
                description=a.get("description"),
                source="MITRE ATT&CK + threat intel feeds",
            )
            db.add(actor)
        db.commit()
        log.info(f"[OSINT] {len(SEED_ACTORS)} acteurs APT initialisés")
        return len(SEED_ACTORS)

    def list_actors(self, db: Session, active_only: bool = False,
                    country: str = None, sponsor: str = None,
                    page: int = 1, per_page: int = 20) -> dict:
        q = db.query(OsintActor).order_by(OsintActor.threat_level.desc())
        if active_only: q = q.filter(OsintActor.is_active == True)
        if country:     q = q.filter(OsintActor.country == country)
        if sponsor:     q = q.filter(OsintActor.sponsor == sponsor)
        total = q.count()
        actors = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "actors": [self._actor_dict(a) for a in actors]}

    def search_actor(self, db: Session, query: str) -> list:
        q = query.lower()
        actors = db.query(OsintActor).all()
        results = []
        for a in actors:
            aliases = json.loads(a.aliases) if a.aliases else []
            sectors = json.loads(a.target_sectors) if a.target_sectors else []
            if (q in a.name.lower() or
                any(q in al.lower() for al in aliases) or
                (a.country and q in a.country.lower()) or
                any(q in s.lower() for s in sectors)):
                results.append(self._actor_dict(a))
        return results[:10]

    def investigate(self, db: Session, target: str,
                    target_type: str = "IP", notes: str = None) -> dict:
        """Lance une investigation OSINT sur un IOC."""
        # Chercher dans la base IOC
        ioc = db.query(ThreatIOC).filter(ThreatIOC.value == target).first()

        reputation = 50
        verdict    = "UNKNOWN"
        sources    = {}

        if ioc:
            reputation = max(0, 100 - ioc.confidence)  # haute confiance = basse réputation
            verdict    = "MALICIOUS"
            sources["IOC_DB"] = f"{ioc.threat_type} ({ioc.source})"

        # Chercher des acteurs liés
        actors = db.query(OsintActor).all()
        related = []
        for a in actors:
            ttps = json.loads(a.primary_ttps) if a.primary_ttps else []
            if ioc and ioc.threat_type and ioc.threat_type in str(a.description):
                related.append(a.name)

        inv = OsintInvestigation(
            target=target, target_type=target_type,
            reputation=reputation, verdict=verdict,
            sources=json.dumps(sources),
            related_actors=json.dumps(related[:3]),
            notes=notes,
        )
        db.add(inv); db.commit(); db.refresh(inv)

        return {"investigation_id": inv.id, "target": target,
                "reputation": reputation, "verdict": verdict,
                "sources": sources, "related_actors": related[:3],
                "ioc_match": bool(ioc)}

    def get_investigations(self, db: Session, page: int = 1, per_page: int = 20) -> dict:
        q = db.query(OsintInvestigation).order_by(desc(OsintInvestigation.investigated_at))
        total = q.count()
        rows  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "investigations": [self._inv_dict(i) for i in rows]}

    def stats(self, db: Session) -> dict:
        total_actors = db.query(OsintActor).count()
        active       = db.query(OsintActor).filter(OsintActor.is_active == True).count()
        investigations = db.query(OsintInvestigation).count()
        malicious    = db.query(OsintInvestigation).filter(OsintInvestigation.verdict == "MALICIOUS").count()
        by_country   = {}
        for a in db.query(OsintActor).all():
            c = a.country or "Unknown"
            by_country[c] = by_country.get(c, 0) + 1
        return {"total_actors": total_actors, "active_actors": active,
                "investigations": investigations, "malicious_targets": malicious,
                "by_country": by_country}

    def _actor_dict(self, a: OsintActor) -> dict:
        return {"id": a.id, "name": a.name,
                "aliases": json.loads(a.aliases) if a.aliases else [],
                "country": a.country, "sponsor": a.sponsor,
                "motivation": json.loads(a.motivation) if a.motivation else [],
                "threat_level": a.threat_level, "sophistication": a.sophistication,
                "is_active": a.is_active, "active_since": a.active_since,
                "target_sectors": json.loads(a.target_sectors) if a.target_sectors else [],
                "target_countries": json.loads(a.target_countries) if a.target_countries else [],
                "primary_ttps": json.loads(a.primary_ttps) if a.primary_ttps else [],
                "description": a.description}

    def _inv_dict(self, i: OsintInvestigation) -> dict:
        return {"id": i.id, "target": i.target, "type": i.target_type,
                "reputation": i.reputation, "verdict": i.verdict,
                "sources": json.loads(i.sources) if i.sources else {},
                "related_actors": json.loads(i.related_actors) if i.related_actors else [],
                "investigated_at": i.investigated_at.isoformat() if i.investigated_at else None}


osint_engine = OsintEngine()
