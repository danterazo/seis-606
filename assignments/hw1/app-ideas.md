# SEIS 606 HW1: Vibe Coding Ideas List
## GitHub & Copilot
I already have a personal GitHub account attached to my UST email address, and I have already redeemed my GitHub Education benefits.

## The List
Homelabbing is a big hobby of mine, so many of the following ideas precede this class. I tried to exclude ideas that could just be scripts, or that would only be useful a single time.

I have a machine with AMD Radeon V620 32GB cards in need of open-weight models to run. That, and the subject of my degree program, inspired these app ideas and their utilization of natural language.


### 1. Natural Language Homelab Management
My server rack is complex, and I often find myself working with Perplexity to debug, manage, and optimize it. For this idea, I envision a dashboard linked to the different tools that power my lab. For example, I run an OpenWRT router, multiple Proxmox nodes, different CPU architectures, and hardware across generations. There are systems that are infrastructure-as-code / stateless and those that are not. There are simply too many paradigms and moving parts to currently manage in one place. It would be helpful to have a tool that can relate nodes to each other and interface with my lab directly.

#### Example Queries
- Create LXC 130 named `adguardhome` using my Ubuntu container template
- Delete all but the last three backups for all containers running Linux
- Pin all containers on my remote node to the latest Ubuntu LTS release
- Run my `xmrig` container for three hours, then report average hashrate
- How many containers have a running Docker daemon?
- Find out why `gluetun` requires so many restarts, and fix it
- Restore LXC 140 to last Thursday's backup
- Do you see any opportunities to improve effiency and/or better allocate resources?
- Which VMs are emulating ARM CPUs?
- Generate an Ansible file that would bring a fresh install as close to my current install as possible


### 2. Home Inventory
I previously tried to inventory parts with Trello, but it wasn't the best tool for the job. For this project, I want to create a dashboard that can help me manage, group, and visualize my tools, parts, and hardware. Ideally I'd define inventory members in terms of each other, i.e. everything is linked by location / type / size / etc.

As a stretch goal, I want to manage food as well. It'd be nice to ask for recipe ideas given my pantry, or get alerts when the cucumbers I just bought will expire.

#### Example Queries
- Add two Noctua fans to my inventory
- Do I have any M3 allen wrenches?
- Add M8 screws to my shopping list
- I used 3 buzzers
  - Implicitly: "Decrement the quantity of piezo buzzers by 3"
- I bought a 50-pack of thick zip ties
  - Implicitly: "Increment the quantity of thick zip ties by 100"


### 3. Home Power Usage Dashboard
I have some smart power plugs that report energy usage, but there is no single place that can manage them all. They live across different apps, and none of them have up-to-date rates. I'm picturing yet another dashboard, but one that summarizes energy usage, understands the nuances of Xcel's energy pricing scheme, and can help paint a picture of what's really going on in my apartment.

Assuming Xcel doesn't have an API, my program would ingest recent electrical bills that I would have to provide manually. Depending on the grain of the information, I might be able to better map and value devices based on what they cost vs. what they provide.

Though controversial, I do find SHA-256 miners fascinating. They are power hungry, though, and not ideal to run 24/7. If I had a better picture of which times/scenarios are cheapest, I could let my program manage which machines are running and when. Alternatively, I could turn them off during high-load periods to lessen the strain on my home circuits (e.g. when my V620 rig is working, the program will prioritize it).

#### Example Queries
- How much has my desktop cost me so far this month? How much does it cost me a week?
- Prioritize my cluster for the next three hours
  - Implicitly: "turn off less-important devices to free up amperage on 15A circuit)
- Never let my track lights be on for more than three hours
- Why is my lamp flickering? Can you identify any machines on the same circuit that might be the cause?
  - This is a real mystery that I've been looking into over the past month.


### 4. Personal Knowledge Base
This is another good opportunity for vibing both the code and the structure/design. I have many different records across different apps (e.g. daily journals in Diarium, sales in Proton Drive, deliveries in Trello, )

obsidian

extension

A stretch goal for this project is digital document management.


### 5. AI Tab Grouping for Sidebery
Firefox now has native AI-powered tab grouping, but I use the Sidebery extension for nested vertical tabs. As such, I can't utilize what Mozilla has already implemented to group _within_ Sidebery. This feature has been requested multiple times, but the developers aren't interested in considering it further.

I want to create a create an app that can interact with Sidebery's API to query tabs, suggest groups, and identify tabs that I forgot to close. for the last one, I'd need training data and/or strongly-defined criteria for which tabs are open for future review, and which ones are probably something I can close (e.g. an article vs. my eBay cart).


### 6. Music Library Standardization & Management
- covers level with files
- no subfolders
- Japanese (romaji + original)



### 7. Aggregated watchlist app
- letterboxd, taiga


### 8. Better Personal Website
