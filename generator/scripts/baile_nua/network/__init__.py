"""S11: the town's electrical network.

Separate from :mod:`baile_nua.engine` because the engine's epoch barrier
aggregates net power and makes no network claim, and this is where a network
claim becomes possible. Keeping them apart is what lets ``NETWORK_CLAIM``
stay true of the engine after this module exists.
"""
