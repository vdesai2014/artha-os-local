from __future__ import annotations

import os
from pathlib import Path

from ..store.projects import StoreCtx, ensure_store_roots

_ctx: StoreCtx | None = None


def init_store() -> StoreCtx:
    global _ctx
    home = Path(os.environ["ARTHA_HOME"]).resolve() if "ARTHA_HOME" in os.environ else Path.cwd().resolve()
    ctx = StoreCtx(home=home)
    ensure_store_roots(ctx)
    _ctx = ctx
    return ctx


def get_ctx() -> StoreCtx:
    assert _ctx is not None, "Store not initialized"
    return _ctx
