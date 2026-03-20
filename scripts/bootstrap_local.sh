#!/usr/bin/env bash
set -euo pipefail

mkdir -p secrets   football/data football/models football/logs   nba/data nba/models nba/logs   nfl/data nfl/models nfl/logs   euroleague/data euroleague/models euroleague/logs   tennis/data tennis/models tennis/logs   shared/output   data/settlement/manual data/settlement/unresolved data/pipeline_runs data/model_registry data/monitoring data/telegram_control data/telegram_control/logs

if [ ! -f secrets/.env ]; then
  cp .env.example secrets/.env
  echo "Created secrets/.env from .env.example"
else
  echo "secrets/.env already exists"
fi

if [ ! -f tennis/models/player_ratings.json ] && [ -f tennis/models/player_ratings.sample.json ]; then
  cp tennis/models/player_ratings.sample.json tennis/models/player_ratings.json
  echo "Created tennis/models/player_ratings.json from sample"
fi

for sport in football nba nfl; do
  if [ ! -f ${sport}/models/player_props_priors.json ] && [ -f ${sport}/models/player_props_priors.sample.json ]; then
    cp ${sport}/models/player_props_priors.sample.json ${sport}/models/player_props_priors.json
    echo "Created ${sport}/models/player_props_priors.json from sample"
  fi
done


for sport in football nba nfl; do
  if [ ! -f data/settlement/manual/${sport}_props_stats.json ] && [ -f shared/manual_settlement_samples/${sport}_props_stats.sample.json ]; then
    cp shared/manual_settlement_samples/${sport}_props_stats.sample.json data/settlement/manual/${sport}_props_stats.json
    echo "Created data/settlement/manual/${sport}_props_stats.json from sample"
  fi
done

echo "Runtime directories prepared."


for sport in football euroleague tennis nba nfl; do
  if [ ! -f data/settlement/manual/${sport}_team_results.json ] && [ -f shared/manual_settlement_samples/${sport}_team_results.sample.json ]; then
    cp shared/manual_settlement_samples/${sport}_team_results.sample.json data/settlement/manual/${sport}_team_results.json
    echo "Created data/settlement/manual/${sport}_team_results.json from sample"
  fi
done
