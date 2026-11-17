#!/usr/bin/env bash
# Download the third-party teams listed in arena/ext_teams.txt into arena/ext_pool/<name>/ (pinned to
# the commit seen at download time, recorded in SOURCE) and install the `train` ones as
# arena/opponents/ext_gh_<name>/. Both locations are gitignored. Already downloaded teams are kept
# as they are (stable benchmark); --refresh re-downloads everything.
#   bash arena/fetch_ext.sh [--refresh]
set -u
cd "$(dirname "$0")/.." || exit 1
P=arena/ext_pool; O=arena/opponents
mkdir -p "$P"
refresh=0; [ "${1:-}" = "--refresh" ] && refresh=1
while read -r set repo _; do
  case "$set" in train|bench|drop) ;; *) continue ;; esac
  n=$(echo "${repo%%/*}" | tr 'A-Z-' 'a-z_'); d=$P/$n
  if [ "$refresh" = 1 ] || [ ! -s "$d/my_team.py" ]; then
    sha=$(git ls-remote "https://github.com/$repo" HEAD 2>/dev/null | cut -f1)
    [ -n "$sha" ] || { echo "FAILED (no HEAD): $repo"; continue; }
    tmp=$(mktemp -d)
    if curl -fsSL --max-time 30 "https://raw.githubusercontent.com/$repo/$sha/my_team.py" -o "$tmp/my_team.py"; then
      # helper modules the team imports from its own repo (e.g. team_utils.py)
      for m in $(grep -oE '^\s*(from|import) +[a-z_][a-z0-9_]*' "$tmp/my_team.py" | awk '{print $2}' | sort -u); do
        case "$m" in random|util|time|math|collections|heapq|itertools|functools|copy|sys|os|json|typing|queue|contest|capture|game|capture_agents|distance_calculator|pyexpat) continue ;; esac
        curl -fsSL --max-time 30 "https://raw.githubusercontent.com/$repo/$sha/$m.py" -o "$tmp/$m.py" 2>/dev/null \
          && echo "  + helper $m.py" || rm -f "$tmp/$m.py"
      done
      rm -rf "$d"; mkdir -p "$d"; cp "$tmp"/*.py "$d/"; echo "$repo $sha" > "$d/SOURCE"
      echo "downloaded $n ($(wc -l < "$d/my_team.py") lines, ${sha:0:7})"
    else
      echo "FAILED (no my_team.py): $repo"
    fi
    rm -rf "$tmp"
  fi
  if [ "$set" = train ] && [ -s "$d/my_team.py" ]; then
    rm -rf "$O/ext_gh_$n"; mkdir -p "$O/ext_gh_$n"; cp "$d"/*.py "$d/SOURCE" "$O/ext_gh_$n/"
  elif [ -d "$O/ext_gh_$n" ]; then
    rm -rf "$O/ext_gh_$n"; echo "removed $O/ext_gh_$n (now '$set')"
  fi
done < arena/ext_teams.txt
echo "training opponents: $(ls -d $O/ext_gh_*/ 2>/dev/null | wc -l)   benchmark: $(grep -c '^bench' arena/ext_teams.txt)"
echo "risky calls (should be empty):"
grep -nE '\b(subprocess|socket|urllib|requests|pickle|exec\(|os\.system|shutil)\b' $P/*/*.py | cut -c1-160
git status --short --untracked-files=all "$P" "$O" | grep ext_gh && echo "WARNING: git sees third-party files!"
exit 0
