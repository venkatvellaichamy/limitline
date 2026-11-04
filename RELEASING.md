# Releasing limitline

Everything lands on `main` through a pull request. `main` is the **dev** channel. Releases are
tags; the release workflow turns a tag into a GitHub release and moves the channel branches.

| Channel | Branch | Moved by | Who runs it |
|---|---|---|---|
| dev | `main` | every merged pull request | development |
| beta | `beta` | every tag (never moved backwards) | trying the next release |
| stable | `stable` | stable tags `vX.Y.Z` only | everyone, day to day |

Claude Code re-installs a plugin only when its version changes, so **every release bumps the
version**, and a beta is `X.Y.Z-beta.N` (also `-alpha.N`, `-rc.N`).

## Cut a release

1. In the pull request that finishes the work:
   - `python3 scripts/version.py bump 0.14.0` (or `0.14.0-beta.1`) writes the version into
     `bin/limitline`, `.claude-plugin/plugin.json`, and `.claude-plugin/marketplace.json`;
   - add `## 0.14.0 - YYYY-MM-DD` to `CHANGELOG.md`; that section becomes the release notes;
   - `python3 scripts/version.py check` must pass (CI runs it on every pull request).
2. Merge the pull request.
3. Tag the merge commit on `main` and push the tag:
   ```sh
   git checkout main && git pull --ff-only
   git tag -a v0.14.0 -m "limitline 0.14.0"
   git push origin v0.14.0
   ```
4. The `release` workflow then checks the tag matches the files and the CHANGELOG, that the
   commit is on `main`, runs the full suite on it, publishes the GitHub release (a prerelease
   for a beta), and moves `beta` (and `stable` for a stable tag).
5. Update a Mac: `limitline update` (or `/plugin marketplace update limitline`).

## Try a beta, then go back

```sh
limitline channel beta --yes     # re-adds the marketplace as #beta and reinstalls
limitline version                # limitline 0.14.0-beta.1 · channel beta (beta)
limitline channel stable --yes
```

A failed release changes nothing: the GitHub release and the branch moves are the last steps.
To withdraw a release, delete the GitHub release, and push the previous tag's commit to
`stable` (or `beta`) by hand.
