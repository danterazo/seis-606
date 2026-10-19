# Pre-Flight Checklist

Before real users touch your app | SEIS 606 Project 1

**Name:** Dante Razo

**App:** Homelab Dashboard

**Date:** 2026-10-18

**How to use:** Work through this on your own app. Mark each box ✓ pass, ✗ fail or ? didn't know how to check. Every fail and ? becomes a row in your test log. Aim for at least three probes you actually ran. A documented failure earns more credit than a hidden one.

## 1. Secrets and Source (about 5 min)

- [ ] Open DevTools (Sources / Network). Any API keys, tokens or passwords visible?
- [ ] View page source. Are answers, hidden scores or "admin" logic visible in client code?
- [ ] Search your repo for key, secret, token, password. Any real values committed?
- [ ] Is .env in .gitignore? Is there a .env.example with fake values?
- [ ] Check git history, not just current files. Was a secret committed once, then deleted?

## 2. Data and Storage (about 5 min)

- [ ] Where does your data live: browser (localStorage), a file, or a database?
- [ ] Edit saved state in DevTools (score, level, user data) and reload. Does the app trust it?
- [ ] If there is a database: who can read and write each table? Can you query it without logging in?
- [ ] Is real personal data in your repo, seed data or screenshots?
- [ ] Is there a backup, or a way to rebuild the data from scratch?

## 3. Auth and Access (about 3 min)

- [ ] Does your app need accounts? If not, write down why that is fine.
- [ ] If yes: skip the UI and hit the URL or API directly. Can you reach things you should not?
- [ ] Are any checks done only in the front end?
- [ ] Did you write your own login, or use a library or service? (Rolling your own is a red flag.)

## 4. Inputs and Edge Cases (about 5 min)

- [ ] Try empty input, very long input, special characters, `<script>` and emoji.
- [ ] Rapid-click, double-submit, refresh mid-action, use the back button.
- [ ] Uploads (if any): wrong file type, huge file, misleading file name.
- [ ] No data, bad data, slow loading: is there an error message, or a blank screen?

## 5. Dependencies and Deployment (about 4 min)

- [ ] Does it run from a fresh clone using only your README? Ask a classmate to try.
- [ ] Are dependency versions pinned? Did you run an audit (npm audit, pip-audit, etc.)?
- [ ] Is debug mode off? Are error pages free of stack traces and file paths?
- [ ] Where would it run, and what happens if the free tier runs out or the service goes down?

## 6. AI-Assisted Review (about 3 min)

- [ ] Give your code to a different AI tool than the one you built with. Prompt it as a security or QA tester.
- [ ] For every finding, record verified, rejected or unsure, plus why.
- [ ] Did it miss something you found by hand? Did it report something that is not real?

## 7. Final Question

**What is the one thing you would fix first, and what is the one thing you could not tell was broken?**

> 

---

# Test Log: Security Probes and Failed Checks

One row per item. Action is **fixed**, **deferred** or **won't fix**. Copy these rows into your project test log.

| Category | What I tested | How | What happened | Action | Severity |
| -------- | ------------- | --- | ------------- | ------ | -------- |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
|          |               |     |               |        |          |
