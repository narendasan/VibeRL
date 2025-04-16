from typing import Optional, Tuple, Callable, List, TypedDict
import logging

import jax
import jax.numpy as jnp

from viberl.algorithms.ppga._rollout import Rollout, make_empty_rollout
from viberl.algorithms.ppga._config import Config
from viberl.algorithms.ppga._state import VPPOState

_LOGGER = logging.getLogger(__name__)

train_fn = Callable[[VPPOState, Config, Rollout, jax.Array, jax.Array, jax.Array], Tuple[jax.Array, jax.Array, jax.Array, jax.Array,  jax.Array, jax.Array, jax.Array, jax.Array]]

returns_fn = Callable[[VPPOState, Config, Rollout], Tuple[jax.Array, jax.Array]]

def batch_update(
    state: VPPOState,
    cfg: Config,
    rollout: Rollout,
    *,
    calculate_returns_fn: returns_fn,
    train_step_fn: train_fn) -> Tuple[jax.Array, jax.Array, jax.Array, jax.Array, jax.Array, List[jax.Array], jax.Array]:

    advantages, returns = calculate_returns_fn(state, cfg, rollout)

    if cfg.normalize_returns:
        returns = state.actors.normalize_returns(returns)

    batch_size = rollout.obs.shape[1]
    minibatch_size = batch_size // cfg.num_minibatches

    batch_idxs = jnp.arange(batch_size)
    clipfracs: List[jax.Array] = []

    pg_loss = v_loss = entropy_loss = ratio = old_approx_kl = approx_kl = jnp.empty(batch_size)

    # TODO: JAXIFY
    for epoch in range(cfg.num_update_epochs):
        for mb_start in range(0, batch_size, minibatch_size):
            mb_end = mb_start + minibatch_size
            mb_idxs = batch_idxs[mb_start : mb_end]
            (loss, pg_loss, v_loss, entropy_loss, old_approx_kl, approx_kl, _clipfracs, ratio) = train_step_fn(state, cfg, rollout, advantages, returns, mb_idxs)
            clipfracs.append(_clipfracs)

        if cfg.target_kl:
            if approx_kl < cfg.target_kl:
                _LOGGER.info(f"Achieved target KL divergance, stopping early at epoch {epoch}")


    return pg_loss, v_loss, entropy_loss, old_approx_kl, approx_kl, clipfracs, ratio
