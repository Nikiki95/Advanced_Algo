#!/usr/bin/env python3
"""
Football Feedback Loop — delegates to shared universal loop.

Usage:
    ./feedback_loop.py                    # Daily check
    ./feedback_loop.py --weekly-retrain   # Weekly retrain
    ./feedback_loop.py --report-only      # Only report
    ./feedback_loop.py --settle-only      # Only settle matches
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from feedback_loop import UniversalBetTracker, print_performance
from utils.result_fetcher import FootballDataFetcher, ResultSettler
from utils.bet_tracker import BetTracker


def run_daily_check(tracker, uni_tracker, settler):
    print(f"\n{'='*60}")
    print(f"⚽ FOOTBALL DAILY CHECK — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*60}")

    # Settle active bets
    print("\n🔍 Settling aktive Bets...")
    settler.settle_all_matches()

    # Performance via universal tracker
    print("\n📈 7-day:")
    perf7 = uni_tracker.calculate_performance(days=7, sport='football')
    print_performance(perf7)

    print("\n📈 30-day:")
    perf30 = uni_tracker.calculate_performance(days=30, sport='football')
    print_performance(perf30)

    return perf30


def run_weekly_retrain(uni_tracker):
    print(f"\n{'='*60}")
    print(f"🔄 FOOTBALL WEEKLY RETRAIN — {datetime.now():%Y-%m-%d}")
    print(f"{'='*60}")

    settled = uni_tracker.get_settled_bets(days=14, sport='football')
    print(f"\n📊 Settled bets (14d): {len(settled)}")

    if len(settled) < 20:
        print("⚠️  Too few bets (< 20). Skipping retrain.")
        return False

    perf = uni_tracker.calculate_performance(days=14, sport='football')
    print(f"   Win-Rate: {perf['win_rate']}% | ROI: {perf['roi_percent']}%")

    if perf['roi_percent'] < -10:
        print(f"⚠️  ROI too negative. Check model parameters!")
        return False

    print("\n🔄 Starting retrain...")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, 'train_all_leagues.py'],
            capture_output=True, text=True, timeout=3600)
        if result.returncode == 0:
            print("   ✅ Retrain successful!")

            # Export Bayesian thresholds for next run
            bayesian = uni_tracker.get_bayesian_export(days=60, sport='football')
            print(f"   📊 Bayesian export: {bayesian.get('total_bets', 0)} bets analyzed")
            return True
        else:
            print(f"   ❌ Retrain failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Football Feedback Loop')
    parser.add_argument('--daily', action='store_true')
    parser.add_argument('--weekly-retrain', action='store_true')
    parser.add_argument('--report-only', action='store_true')
    parser.add_argument('--settle-only', action='store_true')
    args = parser.parse_args()

    tracker = BetTracker()
    uni_tracker = UniversalBetTracker()
    fetcher = FootballDataFetcher()
    settler = ResultSettler(tracker, fetcher)

    if args.settle_only:
        settler.settle_all_matches()
        return

    if args.weekly_retrain:
        run_weekly_retrain(uni_tracker)
        return

    perf = run_daily_check(tracker, uni_tracker, settler)

    print(f"\n{'='*60}")
    print("✅ Football Feedback Loop complete")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
