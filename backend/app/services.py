"""Backward-compatible domain service facade.

New code imports the owning ``app.domain`` module.  This facade prevents older
scripts and integrations from breaking while keeping business ownership split.
"""
from app.domain.common import *  # noqa: F401,F403
from app.domain.media import *  # noqa: F401,F403
from app.domain.reservations import *  # noqa: F401,F403
from app.domain.restrictions import *  # noqa: F401,F403
from app.domain.reviews import *  # noqa: F401,F403
from app.domain.rooms import *  # noqa: F401,F403
from app.domain.settings import *  # noqa: F401,F403
from app.domain.users import *  # noqa: F401,F403
