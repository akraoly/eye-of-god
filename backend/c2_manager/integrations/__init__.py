"""Registre des intégrations C2."""
from c2_manager.models.config import C2Type

# Import des intégrations complètes
from c2_manager.integrations.sliver        import SliverC2
from c2_manager.integrations.empire        import EmpireC2
from c2_manager.integrations.mythic        import MythicC2
from c2_manager.integrations.cobalt_strike import CobaltStrikeC2
from c2_manager.integrations.metasploit    import MetasploitC2

# Stubs (lèvent NotImplementedError)
from c2_manager.integrations.havoc      import HavocC2
from c2_manager.integrations.covenant   import CovenantC2
from c2_manager.integrations.poshc2     import PoshC2C2
from c2_manager.integrations.pupy       import PupyC2
from c2_manager.integrations.koadic     import KoadicC2
from c2_manager.integrations.asyncrat   import AsyncRatC2
from c2_manager.integrations.quasar     import QuasarC2
from c2_manager.integrations.deimos     import DeimosC2
from c2_manager.integrations.villain    import VillainC2
from c2_manager.integrations.redguard   import RedGuardC2
from c2_manager.integrations.bruteratel import BruteRatelC2
from c2_manager.integrations.nighthawk  import NighthawkC2
from c2_manager.integrations.pwndoc     import PwnDocC2
from c2_manager.integrations.faction    import FactionC2

# Mapping C2Type → classe d'intégration
C2_REGISTRY: dict[str, type] = {
    C2Type.SLIVER:        SliverC2,
    C2Type.EMPIRE:        EmpireC2,
    C2Type.MYTHIC:        MythicC2,
    C2Type.COBALT_STRIKE: CobaltStrikeC2,
    C2Type.METASPLOIT:    MetasploitC2,
    C2Type.HAVOC:         HavocC2,
    C2Type.COVENANT:      CovenantC2,
    C2Type.POSHC2:        PoshC2C2,
    C2Type.PUPY:          PupyC2,
    C2Type.KOADIC:        KoadicC2,
    C2Type.ASYNCRAT:      AsyncRatC2,
    C2Type.QUASAR:        QuasarC2,
    C2Type.DEIMOS:        DeimosC2,
    C2Type.VILLAIN:       VillainC2,
    C2Type.REDGUARD:      RedGuardC2,
    C2Type.BRUTE_RATEL:   BruteRatelC2,
    C2Type.NIGHTHAWK:     NighthawkC2,
    C2Type.PWNDOC:        PwnDocC2,
    C2Type.FACTION:       FactionC2,
}

__all__ = [
    "C2_REGISTRY",
    "SliverC2", "EmpireC2", "MythicC2", "CobaltStrikeC2", "MetasploitC2",
    "HavocC2", "CovenantC2", "PoshC2C2", "PupyC2", "KoadicC2",
    "AsyncRatC2", "QuasarC2", "DeimosC2", "VillainC2", "RedGuardC2",
    "BruteRatelC2", "NighthawkC2", "PwnDocC2", "FactionC2",
]
