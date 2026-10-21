# Project 1 Analysis: Homelab Dashboard

## Status

The app runs from the repository and the current local dashboard returned HTTP 200. Its rendered overview showed two online nodes and one unavailable
node, with router DHCP lease panels. The full automated suite passed **264 tests** after two stale test expectations were corrected. Guest
start/reboot, log controls, SSH-backed status collection, router leases, hardware/storage readings, and UI behavior have automated coverage to varying
degrees; guest actions in tests use fake SSH.

This is not a complete match for the original Spec Kit design. The spec and plan describe a read-only dashboard using a dedicated Proxmox API token,
automatic 30-second refresh, ARM-VM filtering, reverse-proxy paths, and specific acceptance criteria. The built application instead uses SSH and
includes guest start/reboot and log-clear controls. It also presents router leases and hardware information that the initial spec did not describe.
The existing convergence section already records some of these gaps, but many older task checkboxes and acceptance criteria do not describe the
shipped code. Treat those design criteria as unverified or unmet, not as features proven by the passing test count.

The app has no login. The user's intended audience is the user alone on a LAN in a single-occupant home. The unauthenticated `/api/status` probe
returned HTTP 200, so any device or person able to reach that endpoint can read the data. LAN-only is not public access, but it is still the
application's technical trust boundary.

## Root Causes

The central gap is design drift: implementation choices and later features moved beyond the original read-only/API-token spec without the spec, plan,
and task list being fully reconciled. That makes a green test suite evidence about the current implementation, not evidence that every original FR or
success criterion is satisfied. The two failures on the first test run were stale expected strings, not runtime defects: the current formatter and
README intentionally preserve hostname text except for explicit token substitutions. Updating those two expectations restored agreement between the
tests and documented behavior; production code did not need modification.

Testing is strongest around deterministic Python logic and API behavior with fake dependencies. That is valuable for avoiding changes to real homelab
systems, but it leaves live integration, an unassisted participant, and an independent AI review unverified. The security test named for secret safety
is also narrow; it does not substitute for a repository and history review.

## Path Forward

1. **Reconcile the as-built spec and task list (1-2 hours).** Decide whether start/reboot/log-clear remain in scope. Update requirements, plan, tasks,
   and acceptance criteria to describe actual SSH integration and behavior, or explicitly mark unmet read-only/API-token requirements as deferred.
   Remove stale claims only after checking the implementation.
2. **Complete the two required human evidence items (45-90 minutes).** Have one person use the dashboard without coaching and record where they
   struggle. Run the required review in a different AI tool than the primary development tool, then independently verify each finding. Do not claim
   either is complete until recorded.
3. **Exercise user-facing edge cases (1-2 hours).** Test page refresh during loading/action, rapid repeated clicks, empty or unavailable sources, and
   recovery after an outage using safe fixtures or a local test instance. Add focused regression tests for any defect found. Do not test by rebooting
   real guests.
4. **Verify a fresh setup and deployment boundary (45-90 minutes).** Follow the README in a clean environment, record dependencies and startup steps,
   review obvious secret exposure/history, and confirm the reverse proxy/firewall cannot expose the no-login service outside the intended LAN.
5. **Close acceptance gaps (estimate after scope decision).** Add tests and implementation only for requirements retained in the reconciled spec,
   including refresh timing, accessibility/responsive behavior, and larger inventory performance where still required.

## Reflection

I would start by making the spec describe one deliberately small, observable workflow and explicitly separating read-only status from any control
actions. During implementation, I would check each user story against the app before marking its task complete, keep tests tied to the changed
behavior, and run the suite after each increment. For AI-generated changes, I would ask for testable claims and inspect the exact code path instead of
treating a plausible summary as proof. Finally, I would reserve time for one outside user and a separate AI review; automated tests cannot stand in
for either requirement.
