# SEIS 606 HW2: App Specs
## Natural Language Homelab Management
I decided to pick my first idea: the NLP Homelab Management dashboard. This project could probably just be a CLI, but I want to create something visually appealing and easy to maintain / expand. It will serve as a one-stop-shop for my many machines and containers

## Objective
<!-- OBJECTIVE: the failure mode, not the feature description -->


## Behavior
<!-- BEHAVIOR: observable outcomes only, no tech details -->


## Constraints
<!-- CONSTRAINTS: non-negotiables regardless of implementation -->


## Verification
<!-- VERIFICATION: testable criteria, not subjective ones -->

## Functionality
### Backend
The app will query MCPs throughout my network and provide a summary of each node. Additionally, it will allow me to perform management tasks (e.g. LXC rollback) using natural language as a proxy for Proxmox commands. In my research, it seems there are already ZFS, Proxmox, Thunderbird (email alerts), and Klipper (rooted 3D printer, also technically a server now) MCPs, but if I need functionality that doesn't already exist, I'll consider that part of this project.

### Frontend
I want to use Streamlit, and if my designs are simply too complex, then I'll find an HTML template out there or generate one myself. This is where I feel less confident, as I haven't been a frontend engineer since 2019. Additionally, though they are cool, I find myself very self-conscious about letting AI dictate design elements. I suppose that defeats the purpose of this class, so I'll get over it.

## Visual Concepts
I tried generating mockups using local models in [image-generation.ipynb](image-generation.ipynb), but this proved to be challenging, and text was always illegible. In my infinite wisdom, I spent the most time on this notebook instead of the actual app outline.

I'm going for a Y2K aesthetic. Even though though the following examples may differ greatly in style, I imagine the final app will look like a combination of them. If I can't balance functionality with design, then I'd prefer a utilitarian approach that prioritizes density.

### Frutiger Aero (Perplexity)
This seems easy to expand and interpret at a glance. I'd be interested in programmatically building the topology instead of hardcoding it.
![Frutiger Aero](mockups/frutiger-perplexity.png)

### Y2K (Perplexity)
This one is a banger, but it seems easy to overcomplicate. I want an app that's easy to maintain, so that means modular, reusable components and programmatic design choices (e.g. automatically retrieving IPs instead of hardcoding them).
![Y2K](mockups/y2k-perplexity.png)

### Y2K Minimal (Perplexity)
This looks clean, but I question how useful it'd be. It also has corny slogans that I don't want. I can foresee this being a panel as part of a bigger page. I'd use circles / progress bars for quick visual validation of load, and I wouldn't bother adding CPU count or uptime. "Samskeyti" is my personal domain, and follows my theme of naming things after Sigur Rós songs. It means "thread" or "connection" in Icelandic, which I felt was fitting. However if this ends up being part of a whole, I won't emphasize the domain name here.
![Y2K (Minimal)](mockups/panel-perplexity.png)
