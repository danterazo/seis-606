# SEIS 606 HW2: App Specs
## Natural Language Homelab Management
I decided to pick my first idea: the NLP Homelab Management dashboard. This project could probably just be a CLI, but I want to create something visually appealing and ideally easy to maintain / expand.

## Functionality
### Backend
The app will query MCPs throughout my network and provide a summary of each node. Additionally, it will allow me to perform management tasks (e.g. LXC rollback) using natural language as a proxy for Proxmox commands. In my research, it seems there are already ZFS, Proxmox, Thunderbird (email alerts), and Klipper (rooted 3D printer, also technically a server now) MCPs, but if I need functionality that doesn't already exist, I'll consider that part of this project.

### Frontend
I want to use Streamlit, and if my designs are simply too complex, then I'll find an HTML template out there or generate one myself. This is where I feel less confident, as I haven't been a frontend engineer since 2019. Additionally, though they are cool, I find myself very self-conscious about letting AI dictate design elements. I suppose that's the whole point of this class, so I'll get over it.
