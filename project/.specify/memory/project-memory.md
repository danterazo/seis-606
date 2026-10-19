# Project Memory

Updated: 2026-10-18

## Operating Decision

- This is a personal homelab dashboard for one operator on the user's own hardware, not a public or multi-user product.
- Keep it local-only and operator-only. Do not broaden access or implement deferred hardening without an explicit request.
- Local-only limits intended reach, not all risk; compromised accounts, browsers, proxies, or LAN devices remain in scope.
- The app defaults to loopback. The README's LAN-access plan conflicts with the user's only-for-my-eyes decision and must be reconciled before implementation.

## Presentation

- Explain the narrow threat model: one operator, personal data and infrastructure, owned homelab hardware, and no public or multi-user access.
- Acknowledge that there is no login, reads expose homelab data, and SSH defaults to root. Local deployment reduces reachability, not code-level risk.
- Be precise about the network boundary. Do not describe LAN access as only-for-my-eyes unless access is actually restricted to the operator.
- Frame additional security work as deferred and proportional to the intended use, not as evidence that the current app is risk-free.

## Deferred Work

These are discussion items, not authorization to change code or deployment. Update status only when the user requests or verifies the work.

- [ ] Reconcile the README's LAN reverse-proxy plan with the operator-only decision; confirm the access boundary before changing deployment guidance.
- [ ] Evaluate least-privilege Proxmox/router reads, including scoped PVE API tokens and restricted probes where suitable.
- [ ] Evaluate reducing root SSH privileges, especially for guest start/reboot actions; retain the current behavior unless a change is explicitly requested.
- [ ] If persistent data is introduced, define dev/production separation, backup/restore, and access controls before deployment.

## Verified Security Posture

As reviewed on 2026-10-18:

- The application defaults to `127.0.0.1`.
- Read endpoints have no user authentication and expose detailed node, guest, device, lease, and activity-log information.
- Guest start/reboot and log-clear writes require loopback and matching same-origin checks plus an app-specific header. These are not user authentication.
- SSH defaults to root and uses public-key authentication, disabled password/keyboard-interactive authentication, batch mode, and strict host-key checking.
- The README proposes LAN clients can read through a reverse proxy; that conflicts with the user's current operator-only decision.
