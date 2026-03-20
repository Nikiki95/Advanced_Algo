# Tennis Module

Implements tournament-based tennis coverage using The Odds API tournament keys.
TheOdds API currently emphasizes **match winner** markets for tennis, with only limited spread/total coverage for selected bookmakers, so this module deliberately focuses on H2H / match winner by default.

Supported out of the box:
- ATP/WTA Indian Wells
- ATP/WTA Miami
- ATP/WTA Madrid
- ATP/WTA Rome
- ATP/WTA Wimbledon
- ATP/WTA US Open

The hybrid model blends bookmaker consensus with optional local player ratings from `tennis/models/player_ratings.json`.
