"""Registry of all active source adapters."""
from sources.baunetz import BauNetzSource
from sources.competitionline import CompetitionlineSource
from sources.architektensuche import ArchitektenSucheSource

ALL_SOURCES = [
    BauNetzSource(),
    CompetitionlineSource(),
    ArchitektenSucheSource(),
]
