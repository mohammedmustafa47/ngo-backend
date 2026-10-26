"""Settings manager: joins the single-concern modules in a fixed order. No logic here."""
from .env import *  # noqa: F401,F403
from .core import *  # noqa: F401,F403
from .security import *  # noqa: F401,F403
from .database import *  # noqa: F401,F403
from .cache import *  # noqa: F401,F403
from .auth import *  # noqa: F401,F403
from .middleware import *  # noqa: F401,F403
from .static import *  # noqa: F401,F403
from .email import *  # noqa: F401,F403
from .logging import *  # noqa: F401,F403
from . import production_check

production_check.check(globals())
