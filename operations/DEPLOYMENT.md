# Oracle Cloud + GoDaddy Deployment Guide

This guide deploys **A Penny Saved** at `https://stopimpulsebuying.us` on one Oracle
Cloud Infrastructure (OCI) virtual machine, with DNS hosted by GoDaddy.

The production path is:

```text
browser -> GoDaddy DNS -> OCI reserved public IP -> Nginx :80/:443
                                                    |-> React static files
                                                    `-> FastAPI 127.0.0.1:8000
                                                          `-> PostgreSQL 127.0.0.1:5432
```

Nginx is the only public application process. FastAPI and PostgreSQL stay on the
instance's loopback interface, so neither port 8000 nor 5432 is opened in OCI or the
host firewall. This is a practical single-server V1 design, but it is not highly
available: an instance, boot-volume, or availability-domain failure can take down both
the app and database. Use tested, encrypted, off-host backups.

> **Before production:** replace every value shown as `REPLACE_WITH_...`, choose named
> owners for deployment, incidents, TLS renewal, and database restores, and resolve the
> blocked decisions in `development/release-decisions.md`. Commands using `sudo` change
> the real server. Read each command before running it.

## 1. Values to collect

Keep these in a password manager or deployment record, not in Git:

| Value | Example in this repository | Why it is needed |
| --- | --- | --- |
| OCI region | closest region to most users | Region affects latency, capacity, and where the reserved IP exists. |
| OCI compartment | `penny-saved-production` | Keeps production resources grouped for IAM, billing, and cleanup. |
| Canonical domain | `stopimpulsebuying.us` | Used by DNS, TLS, Nginx, cookies, CORS, and trusted-host checks. |
| Admin email | `REPLACE_WITH_ADMIN_EMAIL` | Let's Encrypt expiry and recovery contact. |
| Administrator public IPv4/CIDR | `198.51.100.10/32` | Restricts SSH to the administrator instead of the whole internet. |
| Repository URL | `REPLACE_WITH_REPOSITORY_URL` | Source used to create immutable releases. |
| Release commit | full 40-character Git SHA | Makes deployments and rollbacks reproducible. |
| Reserved public IPv4 | assigned later by OCI | Stable address used by GoDaddy DNS. |

The instructions use the repository's configured domain. If the domain changes,
replace it in `operations/production.env.example`,
`operations/nginx/penny-saved.conf.example`, and every command below before deploying.

## 2. Create the OCI compartment and budget

1. Sign in to the OCI Console and select the intended home region. Do not casually
   change regions later: instances, VCNs, and reserved public IPs are regional.
2. Open **Identity & Security -> Compartments**, select the parent compartment, and
   create `penny-saved-production`.
3. Open **Billing & Cost Management -> Budgets**, create a small monthly budget for the
   compartment, and add alert thresholds (for example, 50%, 80%, and 100%). A budget is
   an alert, not a spending cap.
4. Enable multi-factor authentication for the OCI account and avoid routine use of the
   tenancy's root administrator.

**Why:** a dedicated compartment limits the blast radius of permissions and makes
production resources and charges easy to audit. Cost alerts catch a shape, storage,
backup, or network choice that is not covered by Always Free.

## 3. Create the VCN

These instructions deliberately use the **Create VCN** option available in your OCI
Console. No VCN wizard is required. You will create four things separately:

```text
penny-saved-vcn
  -> penny-saved-internet-gateway
  -> penny-saved-public-route-table
  -> penny-saved-public-subnet
```

The order matters because the route table needs the internet gateway, and the subnet
needs the route table.

### 3.1 Create the empty VCN

1. In the OCI Console, confirm the top-bar region is the production region selected in
   section 1.
2. Open the top-left navigation menu.
3. Select **Networking -> Virtual cloud networks**.
4. In the **Compartment** selector on the left, select
   `penny-saved-production`. Wait for the list to refresh.
5. Select **Create VCN**.
6. On the **Create VCN** page or panel, enter:

   | OCI field | Exact value |
   | --- | --- |
   | **VCN name** or **Name** | `penny-saved-vcn` |
   | **Create in compartment** | `penny-saved-production` |
   | **IPv4 CIDR blocks** | `10.0.0.0/16` |
   | **Use DNS hostnames in this VCN** | selected/enabled |
   | **DNS label** | `pennysaved` if OCI asks for one |

7. Do not add another IPv4 CIDR block. Do not add an IPv6 prefix. Leave **Tags** and
   other advanced settings empty/default.
8. Select **Create VCN**.
9. Wait for **Lifecycle state: Available**.

At this point it is normal for the VCN to contain no subnets and have no internet
access. `10.0.0.0/16` is the VCN's private address range; it is not a public IP address.

### 3.2 Create the internet gateway

1. Stay on the `penny-saved-vcn` details page.
2. Depending on your OCI layout, either:
   - select the **Gateways** tab and find **Internet Gateways**; or
   - under **Resources**, select **Internet Gateways**.
3. Select **Create Internet Gateway**.
4. Enter:

   | OCI field | Exact value |
   | --- | --- |
   | **Name** | `penny-saved-internet-gateway` |
   | **Create in compartment** | `penny-saved-production` |

5. If **Route Table Association** appears under advanced options, leave it empty. This
   is a gateway-ingress feature and is not the public subnet route configured next.
6. Select **Create Internet Gateway**.
7. Confirm the new gateway is **Available** or **Enabled**.

The internet gateway is the VCN's path to and from the public internet. Creating it is
not enough by itself; OCI will not use it until the next route rule is added.

### 3.3 Create the public route table

1. Return to the `penny-saved-vcn` details page if necessary.
2. Under **Resources**, select **Route Tables**.
3. Select **Create Route Table**.
4. Enter:

   | OCI field | Exact value |
   | --- | --- |
   | **Name** | `penny-saved-public-route-table` |
   | **Create in compartment** | `penny-saved-production` |

5. Select **+ Another Route Rule**, **+ Additional Route Rule**, or **Add Route Rule**,
   whichever label your console displays.
6. Fill in that one rule:

   | OCI route-rule field | Exact value |
   | --- | --- |
   | **Target Type** | `Internet Gateway` |
   | **Destination Type** | `CIDR Block` if this field appears |
   | **Destination CIDR Block** | `0.0.0.0/0` |
   | **Compartment** | `penny-saved-production` |
   | **Target Internet Gateway** or **Target** | `penny-saved-internet-gateway` |
   | **Description** | `Send public subnet internet traffic to the internet gateway` |

7. Select **Create Route Table**. If the route table was created before the rule was
   entered, open it, select **Add Route Rules**, enter the same values, and save.
8. Open the resulting route table and confirm it shows exactly one explicit rule with
   destination `0.0.0.0/0` and target `penny-saved-internet-gateway`.

`0.0.0.0/0` means every IPv4 destination outside the VCN. OCI also provides an implicit
local route inside the VCN; you do not create or edit that route.

### 3.4 Create the public subnet

1. Return to the `penny-saved-vcn` details page.
2. Under **Resources**, select **Subnets**.
3. Select **Create Subnet**.
4. Enter or select:

   | OCI field | Exact value |
   | --- | --- |
   | **Name** | `penny-saved-public-subnet` |
   | **Create in compartment** | `penny-saved-production` |
   | **Subnet Type** | `Regional` if this field appears |
   | **IPv4 CIDR Block** or **CIDR Block** | `10.0.0.0/24` |
   | **Route Table** | `penny-saved-public-route-table` |
   | **Subnet Access** | `Public Subnet` |
   | **DNS Resolution** | enabled |
   | **DNS Label** | `public` if OCI asks for one |
   | **DHCP Options** | `Default DHCP Options for penny-saved-vcn` |
   | **Security Lists** | `Default Security List for penny-saved-vcn` |

5. The critical public-access control may instead be worded **Prohibit public IP
   addresses on VNICs in this subnet**. If that wording appears, leave the checkbox
   **cleared/off**. Selecting it would make this a private subnet and prevent the web
   server from receiving a public IP address.
6. Leave IPv6, tags, and advanced options at their defaults.
7. Select **Create Subnet** and wait for **Lifecycle state: Available**.

This deployment needs only one subnet. Do not create a private subnet now; PostgreSQL
runs on the same VM and listens only on loopback. A separate private subnet becomes
useful only if the database is moved to another server later.

### 3.5 Verify the finished network

Do not create the compute instance until all five checks pass:

1. `penny-saved-vcn` shows IPv4 CIDR `10.0.0.0/16`.
2. `penny-saved-public-subnet` shows CIDR `10.0.0.0/24` and **Public Subnet**.
3. The subnet is associated with `penny-saved-public-route-table`.
4. That route table contains `0.0.0.0/0 -> penny-saved-internet-gateway`.
5. `penny-saved-internet-gateway` is enabled/available.

The public subnet is where the compute instance will live. The `/24` subnet fits inside
the larger `/16` VCN range. Neither address is exposed on the internet; OCI separately
assigns the instance a real public IPv4 address in section 4.

### Create a network security group

Prefer a network security group (NSG) attached only to this instance over broad edits
to the whole subnet's default security list.

#### Find your administrator public IP before creating the SSH rule

`REPLACE_WITH_ADMIN_PUBLIC_IP` means the public IPv4 address of the computer or
internet connection from which you will SSH into Oracle Cloud. It is **not** the OCI
instance's public IP and it is **not** a local address such as `192.168.x.x`.

On your own computer—not in the OCI Console, Cloud Shell, or compute instance—open a
terminal and run:

```bash
curl -4 https://icanhazip.com
```

For example, if the command prints:

```text
73.184.25.91
```

then use this value as the SSH rule's source:

```text
73.184.25.91/32
```

The `/32` is required. It means that only that one IPv4 address is allowed to attempt
an SSH connection. Do not literally enter `REPLACE_WITH_ADMIN_PUBLIC_IP/32` in OCI.

If `curl` is unavailable, visit `https://icanhazip.com` in a browser on the computer
you will use for SSH and copy the displayed IPv4 address. If the site shows an address
containing colons, that is IPv6; use the `curl -4` command or another "what is my IPv4"
service to obtain IPv4 for this rule.

If you use a VPN, run the command while connected to the VPN and remain connected when
using SSH. If you disconnect, the source address may change. Many home internet
providers also change public IP addresses periodically. If SSH works initially and
later times out, run the command again and update the port 22 source in both the OCI
NSG and the server's UFW rule. Never solve this by permanently opening SSH to
`0.0.0.0/0`.

1. In the VCN, open **Network Security Groups -> Create network security group**.
2. Name it `penny-saved-web-nsg`.
3. Add these **stateful ingress** rules. Leave **Stateless** unchecked and leave source
   port as **All**:

   | Source CIDR | Protocol | Destination port | Purpose |
   | --- | --- | --- | --- |
   | your result plus `/32`, such as `73.184.25.91/32` | TCP | `22` | SSH administration only from your current public IPv4 address. |
   | `0.0.0.0/0` | TCP | `80` | HTTP redirect and ACME certificate validation. |
   | `0.0.0.0/0` | TCP | `443` | Public HTTPS application traffic. |

For the SSH rule, the complete OCI form should be:

| OCI field | Value |
| --- | --- |
| **Stateless** | unchecked |
| **Source Type** | `CIDR` |
| **Source CIDR** | your public IPv4 plus `/32`, such as `73.184.25.91/32` |
| **IP Protocol** | `TCP` |
| **Source Port Range** | leave blank or `All` |
| **Destination Port Range** | `22` |
| **Description** | `SSH from my administrator computer` |

4. Keep the default stateful egress rule allowing `0.0.0.0/0` on all protocols. It is
   needed for OS updates, Git/dependency downloads, DNS, and certificate renewal.
5. Open `penny-saved-public-subnet`, follow its **Default Security List for
   penny-saved-vcn** link, and inspect **Ingress Rules**. If it contains TCP port 22 from
   `0.0.0.0/0`, replace that source with the administrator's `/32` address or remove the
   rule after confirming the NSG rule is attached. The effective permissions are the
   union of security lists and NSGs, so an overly broad rule in either place remains
   open.

Do **not** add ingress for 3000, 5173, 5432, or 8000. Vite is not a production server,
PostgreSQL contains private data, and Uvicorn is reached only through Nginx.

## 4. Create the compute instance

In **Compute -> Instances -> Create instance**, choose:

| Setting | Selection | Why |
| --- | --- | --- |
| Name | `penny-saved-prod-1` | Clear operational identity. |
| Placement | any available AD in the chosen region | A single VM has no cross-AD failover; choose one with shape capacity. |
| Image | **Canonical Ubuntu 24.04 LTS Minimal, aarch64** | Ubuntu 24.04 supplies Python 3.12 and PostgreSQL 16; LTS has a long security-maintenance window. The Arm image matches A1. |
| Shape | **VM.Standard.A1.Flex** | Ampere Arm is OCI's Always Free flexible option and has much more usable memory than E2.1.Micro. |
| OCPUs / memory | **1 OCPU / 6 GB** to start | Enough for this small app and a frontend build while staying within the documented A1 free-tier aggregate. Increase only after measuring and checking cost limits. |
| Boot volume | **50 GB**, default performance, encryption enabled | Accommodates OS, database, logs, releases, and local backup staging; monitor free space. |
| VCN/subnet | `penny-saved-vcn` / `penny-saved-public-subnet` | Required for direct internet access. Select the existing subnet created in section 3. |
| Public IPv4 | temporarily assign an ephemeral IP | Needed for initial SSH; it will be replaced by a reserved IP. |
| NSG | `penny-saved-web-nsg` | Applies only the three intended inbound ports. |

### Complete Step 3: Primary VNIC information / Networking

OCI calls the instance's virtual network card a **VNIC** (virtual network interface
card). The primary VNIC is how this VM joins `penny-saved-vcn`. You are not creating a
second VCN or subnet here; select the existing resources from section 3.

In the instance creation flow, expand **3. Networking**. In some console layouts this
section is titled **Primary VNIC information**. Enter or select the following:

| OCI field | Exact selection or value |
| --- | --- |
| **Primary network** | `Select existing virtual cloud network` |
| **Virtual cloud network (VCN)** | `penny-saved-vcn` |
| **Subnet** | `Select existing subnet` |
| **Subnet name** | `penny-saved-public-subnet` |
| **VNIC name** | `penny-saved-prod-1-vnic` |

If OCI shows a separate compartment selector above either list, select
`penny-saved-production`. If `penny-saved-vcn` or `penny-saved-public-subnet` does not
appear, first confirm that the instance, VCN, and subnet compartments and regions match.
Do not select **Create new virtual cloud network** or **Create new public subnet**.

Under **Primary VNIC IP addresses**, enter:

| OCI field | Exact selection or value | Why |
| --- | --- | --- |
| **Private IPv4 address** | `Automatically assign private IPv4 address` | OCI safely chooses an unused address from `10.0.0.0/24`; there is no need to choose one manually. |
| **Automatically assign public IPv4 address** or **Assign a public IPv4 address** | selected/on | Required for initial SSH and public web traffic. OCI assigns a temporary ephemeral address at creation. |
| **Assign IPv6 addresses from subnet prefixes** | cleared/off | This deployment did not create an IPv6 prefix or IPv6 firewall rules. |

If the public IPv4 option is disabled, greyed out, or absent, stop and fix the subnet:

1. Open **Networking -> Virtual cloud networks -> penny-saved-vcn -> Subnets**.
2. Open `penny-saved-public-subnet`.
3. Confirm it says **Public Subnet**. If OCI instead says **Private Subnet** or
   **Prohibit public IP addresses on VNICs in this subnet: Yes**, the subnet was created
   with the wrong access setting. Recreate the subnet as public using section 3.4; do
   not continue without a public IPv4 address.

Next, find **Network security groups** or expand **Show advanced options** and then the
**Network security groups** area:

1. Select/check **Use network security groups to control traffic**.
2. Select **Add network security group** if OCI presents that button.
3. For the NSG compartment, select `penny-saved-production`.
4. Select `penny-saved-web-nsg`.
5. Confirm it appears in the selected-NSG list before continuing.

Attaching the NSG is essential. Merely creating `penny-saved-web-nsg` does not apply its
SSH, HTTP, and HTTPS rules to the VM.

Under the remaining **Advanced options**, use:

| OCI field | Exact selection or value |
| --- | --- |
| **DNS record** | `Assign a private DNS record` selected/on |
| **Hostname** | `penny-saved-prod-1` if the field is editable; otherwise accept OCI's generated value |
| **Fully qualified domain name** | read-only; accept the displayed value |
| **Launch options** or **Networking type** | `Let Oracle Cloud Infrastructure choose the best networking type` |
| **Route table** / **Use a custom route table for this VNIC** | leave empty/off |
| **Security attributes** / **Zero Trust Packet Routing** | leave empty/default |
| **VNIC tags** | leave empty unless your organization requires tags |

Do not assign a custom route table directly to the VNIC. The VNIC should inherit
`penny-saved-public-route-table` from its subnet; a VNIC-level route table would override
the subnet route and can silently break internet access.

Before leaving step 3, verify this summary:

```text
VCN:             penny-saved-vcn
Subnet:          penny-saved-public-subnet
Private IPv4:    automatically assigned
Public IPv4:     automatically assigned
IPv6:            not assigned
NSG:             penny-saved-web-nsg
Custom route:    none
```

The public IPv4 created here is temporary. Section 5 replaces it with the stable
reserved public IP that will be placed in GoDaddy DNS.

Under SSH keys, upload an existing **Ed25519 public key** or let OCI generate a key and
download the private key immediately. OCI cannot show a generated private key again.
Never email or commit it. On the administrator's computer:

```bash
chmod 600 REPLACE_WITH_PRIVATE_KEY_PATH
ssh -i REPLACE_WITH_PRIVATE_KEY_PATH ubuntu@REPLACE_WITH_EPHEMERAL_IP
```

If A1 capacity is unavailable, try another availability domain or later time. The
fallback **VM.Standard.E2.1.Micro** uses an AMD64 image, but its 1 GB RAM is tight; add
swap, build the frontend elsewhere, and expect lower capacity. Do not choose a paid
shape accidentally.

## 5. Assign a reserved public IP

An ephemeral address is tied to its assignment. A reserved address survives instance
replacement and lets DNS remain stable.

1. Open **Networking -> IP management -> Reserved public IPs**.
2. Select **Reserve public IP address**, name it `penny-saved-prod-ip`, select the
   production compartment and Oracle's default IP pool, then reserve it.
3. Open the compute instance -> **Attached VNICs** -> primary VNIC -> **IPv4 addresses**.
4. Edit the primary private IP's public-IP assignment. Unassign the ephemeral public IP,
   then assign the reserved public IP. Confirm the exact console prompt before saving.
5. Record the reserved IPv4 as `REPLACE_WITH_RESERVED_IP` and reconnect with SSH.

Stopping an instance does not require changing DNS. If the instance is rebuilt, the
same reserved IP can be reassigned to the replacement in the same region.

## 6. Point GoDaddy DNS at OCI

Do this after the reserved address answers SSH and before requesting TLS.

1. Sign in to GoDaddy, open **Domain Portfolio**, select `stopimpulsebuying.us`, then
   open **DNS**.
2. Record the old values before changing them; this is the DNS rollback record.
3. Add or edit the apex record:

   | Type | Name | Value | TTL |
   | --- | --- | --- | --- |
   | A | `@` | `REPLACE_WITH_RESERVED_IP` | 600 seconds if offered, otherwise 1 hour |

4. Add or edit `www`:

   | Type | Name | Value | TTL |
   | --- | --- | --- | --- |
   | CNAME | `www` | `@` (or `stopimpulsebuying.us`) | 1 hour |

5. Remove only conflicting website records for `@` or `www`. Do not alter MX, TXT, or
   mail-related CNAME records. GoDaddy may reject a CNAME when another `www` record
   already exists; edit or remove that specific conflict first.
6. Verify from a machine outside OCI:

```bash
dig +short A stopimpulsebuying.us
dig +short CNAME www.stopimpulsebuying.us
dig +short A www.stopimpulsebuying.us
```

Both names must ultimately resolve to the reserved IP. GoDaddy says most changes are
visible within an hour but global propagation can take up to 48 hours. DNS maps names
to the VM; it does not provide TLS or open a firewall.

## 7. Patch and secure Ubuntu

SSH to the reserved address, then run:

```bash
sudo apt update
sudo apt full-upgrade
sudo apt install --yes nginx postgresql postgresql-contrib python3-venv \
  python3-dev build-essential libpq-dev git curl ca-certificates openssl ufw snapd
sudo reboot
```

Reconnect and confirm the expected platform:

```bash
uname -m
lsb_release -ds
python3 --version
psql --version
nginx -v
```

For the recommended image, `uname -m` should be `aarch64`, Python should be 3.12, and
PostgreSQL should be major version 16. Stop if those assumptions are false.

### Configure the host firewall

OCI rules protect the VNIC; UFW protects the operating system. Both layers must allow a
connection. Add SSH before enabling UFW so the current session is not locked out:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from REPLACE_WITH_ADMIN_PUBLIC_IP to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

Keep the current SSH session open and verify a second SSH login before closing it. If
the administrator's IP changes, add the new `/32` in both OCI and UFW before removing
the old one. Prefer OCI Bastion or a VPN for a team rather than opening SSH globally.

Enable automatic security updates and verify the timers rather than assuming they run:

```bash
sudo apt install --yes unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
systemctl list-timers --all | grep -E 'apt|unattended'
```

Schedule planned reboots after kernel updates; unattended package installation does not
make a newly installed kernel active.

## 8. Create service accounts and directories

The default `ubuntu` user deploys releases. A non-login `penny-saved` user runs the API.

```bash
sudo adduser --system --group --home /nonexistent --no-create-home penny-saved
sudo usermod --append --groups penny-saved ubuntu
sudo usermod --append --groups penny-saved www-data
sudo install -d -o ubuntu -g penny-saved -m 2775 /srv/penny-saved/releases
sudo install -d -o root -g penny-saved -m 0750 /etc/penny-saved
sudo install -d -o postgres -g postgres -m 0750 /var/backups/penny-saved
```

Log out and back in so `ubuntu` receives its new group. The set-group-ID directory
causes new releases to inherit the `penny-saved` group. Nginx gets read-only access to
the frontend via group membership; the API cannot write application releases.

## 9. Configure PostgreSQL

First confirm PostgreSQL listens only on loopback:

```bash
sudo -u postgres psql -tAc "SHOW listen_addresses;"
sudo ss -lntp | grep 5432
```

The listener must be `127.0.0.1`, `::1`, or PostgreSQL's default `localhost`, never
`0.0.0.0` or the instance's VCN address. If needed, set `listen_addresses = 'localhost'`
in `/etc/postgresql/16/main/postgresql.conf`, restart PostgreSQL, and check again.

Generate a database password containing only hexadecimal characters (safe in a URL):

```bash
openssl rand -hex 32
```

Save the output in the password manager, then create the role and database without
putting the password in shell history:

```bash
sudo -u postgres psql
```

At the `postgres=#` prompt:

```sql
CREATE ROLE penny_saved LOGIN;
\password penny_saved
CREATE DATABASE penny_saved OWNER penny_saved;
REVOKE ALL ON DATABASE penny_saved FROM PUBLIC;
\q
```

Paste the generated password twice when `\password` prompts. Test TCP/password auth:

```bash
psql --host=127.0.0.1 --username=penny_saved --password --dbname=penny_saved \
  --command='SELECT current_user, current_database();'
```

The app role owns only its database and is not a PostgreSQL superuser. TCP is used so
the application authenticates with its password rather than local Unix peer identity.

## 10. Install Node.js and create the first release

Install Node 22 for the `ubuntu` deployment user using nvm. Review nvm's current
official installation instructions before running a downloaded installer; the pinned
installer version below is an example, not a permanent trust decision.

```bash
curl -o /tmp/install-nvm.sh https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh
less /tmp/install-nvm.sh
bash /tmp/install-nvm.sh
source "$HOME/.nvm/nvm.sh"
```

Clone and check out the exact reviewed commit:

```bash
cd /srv/penny-saved/releases
git clone REPLACE_WITH_REPOSITORY_URL REPLACE_WITH_FULL_COMMIT_SHA
cd REPLACE_WITH_FULL_COMMIT_SHA
git checkout --detach REPLACE_WITH_FULL_COMMIT_SHA
test "$(git rev-parse HEAD)" = "REPLACE_WITH_FULL_COMMIT_SHA"
nvm install "$(cat .nvmrc)"
npm --prefix frontend ci
npm --prefix frontend run build
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --requirement backend/requirements.txt
```

Run the repository's secret-free checks and confirm the build exists:

```bash
.venv/bin/python scripts/check_operations.py
test -f frontend/dist/index.html
```

`npm ci` uses the lock file, and the backend runtime uses the pinned production
requirements rather than development tools. A detached, full-SHA release directory
cannot silently follow a moving branch. For a private repository, use a read-only deploy
key and remove it from the server if deployments will transfer artifacts another way.

## 11. Create production configuration

Copy the template outside the repository:

```bash
sudo cp operations/production.env.example /etc/penny-saved/backend.env
sudo chown root:penny-saved /etc/penny-saved/backend.env
sudo chmod 0640 /etc/penny-saved/backend.env
sudoedit /etc/penny-saved/backend.env
```

Replace:

- `REPLACE_WITH_DATABASE_PASSWORD` with the hexadecimal PostgreSQL password.
- `REPLACE_WITH_RANDOM_RATE_LIMIT_KEY_32_BYTES_MINIMUM` with a different secret from
  `openssl rand -hex 32`.

Do not reuse passwords or commit this file. Because a SQLAlchemy URL is used, a password
with characters such as `@`, `:`, `/`, or `%` would need percent-encoding; the generated
hex password avoids that error. The file already enables secure cookies, exact origins,
trusted hosts, proxy restrictions, JSON logs, and request-size/rate limits for
`stopimpulsebuying.us`.

Validate configuration construction without printing secrets:

```bash
cd /srv/penny-saved/releases/REPLACE_WITH_FULL_COMMIT_SHA/backend
sudo systemd-run --wait --pipe --collect --unit=penny-saved-config-check \
  --uid=penny-saved --gid=penny-saved \
  --property=WorkingDirectory="$PWD" \
  --property=EnvironmentFile=/etc/penny-saved/backend.env \
  /srv/penny-saved/releases/REPLACE_WITH_FULL_COMMIT_SHA/.venv/bin/python \
  -c 'from app.main import create_app; create_app(); print("configuration valid")'
```

## 12. Back up, migrate, and activate the release

For the first empty database, record that no pre-migration data exists. On every later
release, take and verify a backup first as described in section 17.

Apply migrations in transient systemd units that read the protected environment file.
This avoids expanding database credentials into the command line or interactive shell:

```bash
cd /srv/penny-saved/releases/REPLACE_WITH_FULL_COMMIT_SHA/backend
sudo systemd-run --wait --pipe --collect --unit=penny-saved-migrate \
  --uid=penny-saved --gid=penny-saved \
  --property=WorkingDirectory="$PWD" \
  --property=EnvironmentFile=/etc/penny-saved/backend.env \
  /srv/penny-saved/releases/REPLACE_WITH_FULL_COMMIT_SHA/.venv/bin/python \
  -m alembic upgrade head
sudo systemd-run --wait --pipe --collect --unit=penny-saved-migration-status \
  --uid=penny-saved --gid=penny-saved \
  --property=WorkingDirectory="$PWD" \
  --property=EnvironmentFile=/etc/penny-saved/backend.env \
  /srv/penny-saved/releases/REPLACE_WITH_FULL_COMMIT_SHA/.venv/bin/python \
  -m alembic current
```

Activate the release with an atomic symlink:

```bash
sudo ln -s /srv/penny-saved/releases/REPLACE_WITH_FULL_COMMIT_SHA \
  /srv/penny-saved/current.next
sudo mv -T /srv/penny-saved/current.next /srv/penny-saved/current
```

## 13. Install and start the systemd service

```bash
sudo cp /srv/penny-saved/current/operations/systemd/penny-saved.service.example \
  /etc/systemd/system/penny-saved.service
sudo systemd-analyze verify /etc/systemd/system/penny-saved.service
sudo systemctl daemon-reload
sudo systemctl enable --now penny-saved
sudo systemctl status penny-saved --no-pager
curl --fail --silent --show-error http://127.0.0.1:8000/api/health
curl --fail --silent --show-error http://127.0.0.1:8000/api/ready
sudo ss -lntp | grep 8000
```

Port 8000 must show `127.0.0.1`, not `0.0.0.0`. If startup fails:

```bash
sudo journalctl -u penny-saved --since '10 minutes ago' --no-pager
```

The service runs as `penny-saved`, restarts after unexpected failures, and does not run
migrations automatically. Keeping migrations explicit makes backup and rollback checks
possible.

## 14. Bootstrap Nginx and obtain TLS

The final checked-in Nginx configuration references certificate files that do not exist
yet. Start with HTTP only:

```bash
sudo install -d -o www-data -g www-data -m 0755 /var/www/letsencrypt
sudo tee /etc/nginx/sites-available/penny-saved-bootstrap >/dev/null <<'NGINX'
server {
    listen 80;
    listen [::]:80;
    server_name stopimpulsebuying.us www.stopimpulsebuying.us;
    root /srv/penny-saved/current/frontend/dist;

    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto http;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/penny-saved-bootstrap \
  /etc/nginx/sites-enabled/penny-saved-bootstrap
sudo nginx -t
sudo systemctl reload nginx
curl -I http://stopimpulsebuying.us
```

The `rm` removes only Ubuntu's default enabled-site symlink, not application data. If
the curl cannot connect, check DNS, the OCI NSG, the subnet security list, UFW, and
Nginx before continuing.

Install Certbot from its recommended snap distribution and request both names:

```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/local/bin/certbot
sudo certbot certonly --webroot --webroot-path /var/www/letsencrypt \
  --domain stopimpulsebuying.us --domain www.stopimpulsebuying.us \
  --email REPLACE_WITH_ADMIN_EMAIL --agree-tos --no-eff-email
```

Now install the repository's final configuration:

```bash
sudo cp /srv/penny-saved/current/operations/nginx/penny-saved.conf.example \
  /etc/nginx/sites-available/penny-saved
sudo ln -s /etc/nginx/sites-available/penny-saved \
  /etc/nginx/sites-enabled/penny-saved
sudo rm /etc/nginx/sites-enabled/penny-saved-bootstrap
sudo nginx -t
sudo systemctl reload nginx
sudo certbot renew --dry-run
systemctl list-timers --all | grep certbot
```

Never reload after a failed `nginx -t`. Certbot's renewal timer renews the certificate;
the dry run proves the validation and reload path before expiry.

## 15. End-to-end verification

Run from outside the OCI instance:

```bash
curl --fail --silent --show-error https://stopimpulsebuying.us/api/health
curl --fail --silent --show-error https://stopimpulsebuying.us/api/ready
curl --head http://stopimpulsebuying.us
curl --head https://www.stopimpulsebuying.us
```

Confirm HTTP and `www` redirect to canonical HTTPS. In a private/incognito browser:

1. Open `https://stopimpulsebuying.us` and confirm the certificate is valid.
2. Sign up with a new production test account.
3. Log out and back in.
4. Create, edit, and delete a disposable entry.
5. Confirm a refresh retains the authenticated session.

On the server, confirm only intended public listeners and private app/database ports:

```bash
sudo ss -lntp
curl --fail --silent --show-error http://127.0.0.1:8000/internal/metrics | head
curl --fail --silent --show-error --output /dev/null --write-out '%{http_code}\n' \
  https://stopimpulsebuying.us/internal/metrics
```

The public metrics request must be `404`. Record the release SHA, migration revision,
test time, operator, and results.

## 16. Routine releases

For each reviewed full commit SHA:

1. Run `make check`, `make security-check`, `make rehearse-restore`, and `make e2e` in a
   trusted build environment.
2. Create `/srv/penny-saved/releases/<full-SHA>`, build its frontend, and create its
   virtual environment as in section 10. Never overwrite an existing release.
3. Check disk bytes and inodes with `df -h` and `df -i`; stop below the runbook's 20%
   free-space threshold.
4. Create and verify an off-host database backup.
5. Review `alembic current`, `alembic heads`, and pending migration code. Confirm the old
   app can run against the new schema.
6. Apply `alembic upgrade head` from the new release.
7. Atomically repoint `/srv/penny-saved/current` to the new release.
8. Run `sudo nginx -t`, then `sudo systemctl restart penny-saved` and reload Nginx only
   if its configuration changed.
9. Repeat health, readiness, browser, log, and metrics checks through an agreed
   observation window.

Follow `operations/RELEASE.md` for the release-control evidence and stop/go criteria.

### Application rollback

If the database schema remains backward-compatible, repoint `current` to the recorded
previous full-SHA directory, restart the service, and verify again:

```bash
sudo ln -s /srv/penny-saved/releases/REPLACE_WITH_PREVIOUS_FULL_SHA \
  /srv/penny-saved/current.next
sudo mv -T /srv/penny-saved/current.next /srv/penny-saved/current
sudo systemctl restart penny-saved
```

Do not automatically run `alembic downgrade` or restore an older database. Database
rollback can destroy newer user data and requires a migration-specific, approved
recovery plan.

## 17. Backups and restore tests

The VM is not a backup destination. At minimum, store encrypted database dumps outside
the instance (for example, in a private OCI Object Storage bucket with versioning and
retention, or another approved encrypted provider). Protect the bucket with least-
privilege IAM and lifecycle rules. Choose and record retention, recovery point objective
(RPO), recovery time objective (RTO), and the restore owner.

Create a local staging dump without putting a password on the command line. Configure a
root-owned PostgreSQL service file or `.pgpass` first, then:

```bash
sudo -u postgres sh -c 'umask 077; pg_dump --dbname=penny_saved --format=custom \
  --no-owner --no-acl --file=/var/backups/penny-saved/penny_saved_REPLACE_WITH_UTC_TIMESTAMP.dump'
sudo -u postgres pg_restore --list \
  /var/backups/penny-saved/penny_saved_REPLACE_WITH_UTC_TIMESTAMP.dump >/dev/null
sudo sha256sum /var/backups/penny-saved/penny_saved_REPLACE_WITH_UTC_TIMESTAMP.dump
```

Encrypt and upload the dump using the approved tool, verify the remote object and
checksum, then remove local staging copies according to policy. A successful upload is
not proof of recovery. On a separate non-production PostgreSQL 16 target, download,
decrypt, verify the checksum, restore with `pg_restore --exit-on-error`, and check the
Alembic revision and representative row counts. Record evidence regularly and before
high-risk releases. The more detailed safety constraints are in `operations/README.md`.

Also protect the ability to rebuild: retain the Git repository, exact lock files,
deployment guide, environment schema (not secret values), OCI configuration record, and
encrypted secret recovery material. An OCI boot-volume backup can shorten recovery but
does not replace an independent database dump.

## 18. Monitoring and maintenance

At a minimum:

- Check `/api/ready` externally and alert after repeated failures.
- Monitor disk bytes/inodes, memory, CPU, PostgreSQL space/connections, systemd restart
  count, HTTP error rate, latency, certificate expiry, and backup age.
- Bound systemd journal storage in `/etc/systemd/journald.conf.d/`; logs contain user IDs
  and operational metadata and must have restricted access.
- Review `sudo journalctl -u penny-saved`, Nginx logs, OCI Audit logs, and UFW status
  during incidents without copying cookies, request bodies, or secrets.
- Apply OS security updates, dependency updates, and planned reboots through a tested
  release and rollback process.
- Test `sudo certbot renew --dry-run` after networking or Nginx changes.
- Review OCI cost and Always Free usage; free-tier eligibility and capacity are not an
  availability guarantee.

Useful commands:

```bash
systemctl is-active nginx postgresql penny-saved
sudo journalctl -u penny-saved --since '15 minutes ago' -o cat
df -h
df -i
free -h
sudo -u postgres psql -tAc 'SELECT version();'
sudo certbot certificates
```

## 19. Troubleshooting map

| Symptom | Check in this order |
| --- | --- |
| SSH times out | current admin IP, OCI NSG port 22 source, subnet security list, reserved-IP assignment, UFW |
| Domain resolves to wrong IP | GoDaddy `@` A record, conflicting records, resolver cache, reserved IP |
| Port 80/443 times out | OCI NSG, security list, route to internet gateway, UFW, Nginx status |
| Nginx will not start before TLS | use only the bootstrap HTTP configuration until certificate files exist |
| `502 Bad Gateway` | `penny-saved` service, journal, loopback port 8000, readiness, file permissions |
| `/api/ready` is `503` | PostgreSQL status/listener, credentials, disk, connection limits, application journal |
| Login fails only in browser | exact HTTPS `FRONTEND_ORIGIN`, secure cookie, system clock, Origin header, trusted host |
| Frontend route returns 404 on refresh | Nginx `try_files ... /index.html` and correct `frontend/dist` path |
| Certbot validation fails | both DNS names resolve here, port 80 public, challenge root, no conflicting redirect/config |
| A1 build crashes | memory/disk pressure; build on a compatible Arm runner or carefully add swap, then measure capacity |

## Official references

- [OCI Virtual Networking Wizards](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/quickstartnetworking.htm)
- [OCI public-subnet networking scenario](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/scenarioa.htm)
- [OCI internet gateway configuration](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingIGs.htm)
- [OCI creating a compute instance](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm)
- [OCI Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
- [OCI reserved public IPs](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/reserved-public-ip-create.htm)
- [GoDaddy A-record instructions](https://www.godaddy.com/help/edit-an-a-record-19239)
- [Certbot Nginx instructions](https://certbot.eff.org/instructions?ws=nginx&os=snap)
- [Ubuntu Server web-service documentation](https://documentation.ubuntu.com/server/how-to/web-services/)

Cloud consoles, pricing, available images, and package versions change. This guide was
checked against the linked official documentation on **2026-08-13**. Reconfirm the image,
shape price/free-tier marker, and console labels at deployment time.
