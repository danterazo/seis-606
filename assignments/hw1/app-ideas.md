# SEIS 606 HW1: Vibe Coding Ideas List
## GitHub & Copilot
I already have a personal GitHub account attached to my UST email address, and I have already redeemed my GitHub Education benefits.

## The List
Homelabbing is a big hobby of mine, so many of the following ideas precede this class. I tried to exclude ideas that could just be scripts, or that would only be useful a single time.

I have a machine with AMD Radeon V620 32GB cards in need of open-weight models to run. That, and the subject of my degree program, inspired these app ideas and their utilization of natural language. The example queries aren't indication that each project will be a chatbot — instead, they paint a picture of what information and value each app provides.


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
This is another good opportunity for vibing both the code and the structure/design. I have many different records across different apps (e.g. daily journals in Diarium, sales in Proton Drive, deliveries in Trello, etc.) and no great way to consolidate and map content to each other. I have been interested in Obsidian due to its plaintext backing files and extensibility, but I haven't been able to sit down and customize it to my heart's content yet. It would be nice to have a tool, whether that's an Obsidian plugin or yet another dashboard, that can help me keep track of my records and documents. Emails would be an important source of information, though bloated with newsletters and less-personal messages.

In additional to managing records, it would be great for this project to have a high-level understanding of my digital document organization "style," and be able to group common, loose files together. So in additional to containing knowledge, it also knows where else to find what I'm looking for.

#### Example Queries
- On which day of the week do I ride the farthest on my bike?
- How often are rainy days rated low?
- How many shirts have I sold on eBay? What was the average price per shirt before S&H?
- When did I unsubscribe from Arnold Schwarzenegger's newsletter?
- In which semester did I take *Data Analytics*?
- How does class influence the length of my journal entries
  - In other words, do I write less or more on days that I have class


### 5. AI Tab Grouping for Sidebery
Firefox now has native AI-powered tab grouping, but I use the Sidebery extension for nested vertical tabs. As such, I can't utilize what Mozilla has already implemented to group *within* Sidebery. This feature has been requested multiple times, but the developers aren't interested in considering it further.

I want to create a create an app that can interact with Sidebery's API to query tabs, suggest groups, and identify tabs that I forgot to close. for the last one, I'd need training data and/or strongly-defined criteria for which tabs are open for future review, and which ones are probably something I can close (e.g. an article vs. my eBay cart).

The program will also hook into Firefox's browsing history to understand interests, relationships between sites/topics (e.g. sites often opened after specific others), and the manner in which I browse the web.

#### Example Queries
- How many Wikipedia tabs do I have open?
- How many nested YouTube tabs are there?
- Which topics tend to spawn the most child/nested tabs?
- In the current panel, group 3D model tabs by {website, category, estimated size, download count}
  - Real life example: I have a panel of 3D-printed model pages, each manually grouped into folders
- How long to I tend to spend on Amazon between searching an item and finally checking out?
  - In this case, the initial search + the "checkout" URL would provide a bound on time spent


### 6. Music Library Standardization & Management
I have a particular style when it comes to tagging music files and organizing them in my library. For example, I like to have a single picture called "cover.jpg" alongside files, compress lyrics files into "lyrics.7z," utilize macrons for long vowels in Japanese song titles, and save files in lowercase. I'd like a tool that can automatically identify existing "rules" for organizing and apply them to the entire library, since there are definitely some folders that are missing inline album art for example. I foresee a web page or some sort of interface that can ingest new files and automatically apply transformations on my behalf.


### 7. Aggregated Media Library Statistics
It wouldn't be very useful, but it'd be neat to visualize all my media consumption in one place. It would crunch numbers and present fun, dynamically-generated stats cards such as:
- Songs never listened to
- Movies that were watched within a day of being added to the library
- Most popular documentary topic
- Most popular genre on Thursdays

With integration to the other app ideas above, I could even ask questions such as:
- Which albums do I listen to most on rough days
  - Implicitly: "On days rated ⅕ on Diarium, which albums do I reach for first?"
- Which movies tend to lift my spirits the day after watching them?
- When was the last time I listened to *The Ocean Blue*?
