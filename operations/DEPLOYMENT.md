# Oracle Cloud + GoDaddy Deployment Guide

This guide deploys **A Penny Saved** at `https://stopimpulsebuying.online` on one Oracle
Cloud Infrastructure (OCI) virtual machine, with DNS hosted by GoDaddy.

The production path is:

```text
browser -> GoDaddy DNS -> OCI ephemeral public IP -> Nginx :80/:443
                                                    |-> React static files
                                                    `-> FastAPI 127.0.0.1:8000
                                                          `-> PostgreSQL 127.0.0.1:5432
```

Nginx is the only public application process. FastAPI and PostgreSQL stay on the
instance's loopback interface, so neither port 8000 nor 5432 is opened in OCI or the
host firewall. This is a practical single-server V1 design, but it is not highly
available: an instance, boot-volume, or availability-domain failure can take down both
the app and database. Use tested, encrypted, off-host backups.

This guide uses one compute profile throughout: **VM.Standard.E2.1.Micro** with the
**Canonical Ubuntu 24.04 Minimal** image (the entry without `aarch64`), a 2 GB swap
file, and one Uvicorn worker. It is intentionally sized for approximately one or two
simultaneous users. Do not select **Canonical Ubuntu 24.04 Minimal aarch64**; that image
is for an Arm shape, not the AMD-based E2.1.Micro shape.

> **Before production:** replace every value shown as `REPLACE_WITH_...`, choose named
> owners for deployment, incidents, TLS renewal, and database restores, and resolve the
> blocked decisions in `development/release-decisions.md`. Commands using `sudo` change
> the real server. Read each command before running it.

## 1. Values to collect

Keep these in a password manager or deployment record, not in Git:

| Value | Example in this repository | Why it is needed |
| --- | --- | --- |
| OCI region | closest home region to most users | Region affects latency, capacity, and where the instance and public IP exist. |
| OCI compartment | `penny-saved-production` | Keeps production resources grouped for IAM, billing, and cleanup. |
| Canonical domain | `stopimpulsebuying.online` | Used by DNS, TLS, Nginx, cookies, CORS, and trusted-host checks. |
| Admin email | `REPLACE_WITH_ADMIN_EMAIL` | Let's Encrypt expiry and recovery contact. |
| Administrator public IPv4/CIDR | `198.51.100.10/32` | Restricts SSH to the administrator instead of the whole internet. |
| Repository URL | `REPLACE_WITH_REPOSITORY_URL` | Source used to create immutable releases. |
| Release commit | full 40-character Git SHA | Makes deployments and rollbacks reproducible. |
| Public IPv4 | `132.145.170.34` | Current ephemeral internet address used by SSH and GoDaddy DNS. Public IPs are not secrets, but this value must be updated if the VM/VNIC is replaced. |

The instructions use the repository's configured domain. If the domain changes,
replace it in `operations/production.env.example`,
`operations/nginx/penny-saved.conf.example`, and every command below before deploying.

## 2. Create the OCI compartment and budget

1. Sign in to the OCI Console and select the intended home region. Do not casually
   change regions later: instances, VCNs, and public IP resources are regional.
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
| Placement | the AD in which OCI offers `VM.Standard.E2.1.Micro`; fault domain set to **Let Oracle choose** | OCI offers E2.1.Micro in only one AD in multi-AD regions. A single VM has no cross-AD failover. |
| Image | **Canonical Ubuntu 24.04 Minimal**—specifically the entry without `aarch64` | Ubuntu 24.04 supplies Python 3.12 and PostgreSQL 16. The generic entry is the correct x86_64 image for E2.1.Micro; the separately labeled `aarch64` entry is not. |
| Shape | **VM.Standard.E2.1.Micro** | This is OCI's fixed-size Always Free AMD micro shape and is sufficient for the expected one or two simultaneous users. |
| OCPUs / memory | fixed by OCI: burstable **1/8 OCPU and 1 GB RAM** | These values are not editable for E2.1.Micro. The required swap and one-worker configuration later in this guide accommodate the small memory limit. |
| Boot volume | **50 GB**, default performance, encryption enabled | Accommodates OS, database, logs, releases, and local backup staging; monitor free space. |
| VCN/subnet | `penny-saved-vcn` / `penny-saved-public-subnet` | Required for direct internet access. Select the existing subnet created in section 3. |
| Public IPv4 | automatically assign an ephemeral IP | Needed for SSH and public web traffic. Keep and record this address in section 5. |
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

The public IPv4 created here is ephemeral. Section 5 verifies it and records it for
GoDaddy DNS.

### Complete the SSH keys section

The SSH key proves to the server that your computer is authorized to log in. It has two
parts:

- the **public key** is safe to place on the OCI instance; and
- the **private key** must remain secret on your personal computer.

The order of operations is:

```text
1. Download/save the private key while filling out the OCI instance form.
2. Finish the form and select Create.
3. Wait for the OCI instance to show Running.
4. Copy the instance's Public IPv4 address from OCI.
5. Open Terminal on your Mac and run ssh using the private key and public IP.
```

Do not try to SSH immediately after downloading the key while the instance form is
still open. The key file exists at that point, but there is no running server or public
IP to connect to yet.

Choose exactly one of the following OCI options.

#### Option A: Let OCI generate the key pair (recommended if you do not have a key)

1. In the instance form's **Add SSH keys** section, select **Generate a key pair for
   me**.
2. Select **Save private key** and download the private-key file.
3. You may also select **Save public key** for your records, but it is not required for
   connecting. OCI automatically installs that public key on the new instance.
4. Do not finish creating the instance until the private-key download is complete. OCI
   cannot display or download this private key again later.

You need the downloaded **private key** to connect. You do not pass the downloaded
public-key file to the `ssh` command. OCI-generated downloads commonly look similar to:

```text
ssh-key-2026-08-16.key       <- PRIVATE key: use this with ssh -i
ssh-key-2026-08-16.key.pub   <- PUBLIC key: do not use this with ssh -i
```

The `.pub` suffix means "public key." If your intended path ends in `.pub`, stop and
select the matching file without `.pub`. If you saved only the `.pub` file and did not
save the private key, that public file cannot be converted into the private key. Before
creating the instance, use **Save private key**; after creating it, you would need to
install a different public key through an OCI recovery method or recreate the instance.

#### Option B: Upload a public key you already own

Select **Upload public key files** or **Paste public keys**, then provide your existing
`.pub` key. In this case, do not download or generate another key: connect using the
matching private key already stored on your computer. For example, an uploaded
`~/.ssh/id_ed25519.pub` matches the private key `~/.ssh/id_ed25519`.

Never upload, paste, email, or commit a private key. Do not store it in this repository.

### Create the instance and find its temporary public IP

After reviewing the remaining instance settings, select **Create**. Wait until the
instance's **State** or **Lifecycle state** becomes **Running**. Then:

1. Open **Compute -> Instances -> penny-saved-prod-1**.
2. On the instance details page, find **Public IPv4 address** or **Public IP address**.
3. Copy that address. For this deployment it is currently `132.145.170.34`. It is a
   public address, not the private `10.0.0.x` address.

Do not use the **Private IPv4 address** beginning with `10.`. That private address is
not reachable directly from your personal computer.

### Connect from macOS or Linux

Run the following commands in the Terminal application on your **personal computer**.
Do not run them in OCI Cloud Shell, the browser console, or this project's server.

If OCI downloaded a file such as `ssh-key-2026-08-15.key` into your Downloads folder,
move it into your SSH folder and give it a recognizable name:

```bash
mkdir -p "$HOME/.ssh"
mv "$HOME/Downloads/ssh-key-2026-08-15.key" "$HOME/.ssh/penny-saved-oci.key"
chmod 600 "$HOME/.ssh/penny-saved-oci.key"
```

Replace `ssh-key-2026-08-15.key` with the exact downloaded private-key filename. The
`chmod 600` command permits only your user account to read or change the private key;
OpenSSH commonly refuses keys with broader permissions.

For the concrete example of macOS user `angelahu` with files downloaded on August 16,
the private-key source path is:

```text
/Users/angelahu/Downloads/ssh-key-2026-08-16.key
```

It is **not**:

```text
/Users/angelahu/Downloads/ssh-key-2026-08-16.key.pub
```

To verify both downloaded files before moving anything, run this in Terminal on the
Mac:

```bash
ls -l /Users/angelahu/Downloads/ssh-key-2026-08-16.key*
```

Then move and secure only the private file:

```bash
mkdir -p /Users/angelahu/.ssh
mv /Users/angelahu/Downloads/ssh-key-2026-08-16.key \
  /Users/angelahu/.ssh/penny-saved-oci.key
chmod 600 /Users/angelahu/.ssh/penny-saved-oci.key
```

It is correct that this private key remains on the Mac while the server runs Ubuntu.
SSH is a connection between two different computers: the Mac's SSH client reads the
private key locally, and the Ubuntu VM checks it against the corresponding public key
OCI installed on the VM. Never upload the private key to the Ubuntu VM.

Connect using the current public IPv4 copied from the OCI instance page:

```bash
ssh -i "$HOME/.ssh/penny-saved-oci.key" ubuntu@132.145.170.34
```

For this deployment, these values mean:

```text
Private key path = $HOME/.ssh/penny-saved-oci.key
Ephemeral IP     = 132.145.170.34
Login username   = ubuntu
```

The first connection normally asks whether to trust the host fingerprint. Confirm the
IP is the one shown by OCI, type `yes`, and press Enter. A successful login changes the
prompt to one on the Ubuntu instance. Run `whoami`; it should print `ubuntu`.

If you uploaded an existing public key instead, substitute its matching private-key
path. For example:

```bash
chmod 600 "$HOME/.ssh/id_ed25519"
ssh -i "$HOME/.ssh/id_ed25519" ubuntu@132.145.170.34
```

#### Connect from Windows PowerShell

Run these commands in **PowerShell on your personal Windows computer**. Replace the
filename and IP with your real values:

```powershell
New-Item -ItemType Directory -Force "$HOME\.ssh"
Move-Item "$HOME\Downloads\ssh-key-2026-08-15.key" "$HOME\.ssh\penny-saved-oci.key"
icacls "$HOME\.ssh\penny-saved-oci.key" /inheritance:r
icacls "$HOME\.ssh\penny-saved-oci.key" /grant:r "$($env:USERNAME):(R)"
ssh -i "$HOME\.ssh\penny-saved-oci.key" ubuntu@132.145.170.34
```

Windows uses `icacls` rather than `chmod` to restrict the key. Recent Windows versions
include the OpenSSH `ssh` command. If PowerShell reports that `ssh` is unknown, install
the Windows **OpenSSH Client** optional feature, reopen PowerShell, and retry.

If SSH times out, check the instance is running, the public IP is correct, and the OCI
NSG port 22 source still matches your current public IPv4 from the earlier
`curl -4 https://icanhazip.com` check. If SSH says `Permission denied (publickey)`, the
selected private key does not match the public key installed on the instance, the login
username is wrong, or the private-key file permissions are too broad.

### Confirm the E2 image, shape, and placement

In **Image and shape**, select **Change image** and choose exactly:

```text
Canonical Ubuntu 24.04 Minimal
```

OCI may show these two similar choices:

```text
Canonical Ubuntu 24.04 Minimal aarch64  <- do not select for E2.1.Micro
Canonical Ubuntu 24.04 Minimal          <- select this one
```

The unlabeled/generic second entry is the x86_64 image used by the AMD-based
E2.1.Micro shape. If OCI displays image details, confirm **Architecture** says
`x86_64` or `AMD64`; the absence of `aarch64` in the image name is the important
distinction in the picker. Then select **Change shape -> Specialty and previous generation ->
VM.Standard.E2.1.Micro** (the shape-category wording can vary).

Confirm the shape row says **Always Free eligible** before creating the instance. Do
not assume another similarly named E-series shape is free. Oracle documents
E2.1.Micro as 1 GB RAM, burstable 1/8 OCPU, and limited public bandwidth. It is a good
cost-conscious fit for one or two simultaneous users, but updates and frontend builds
will be slow.

#### If OCI says "Some resource limit is critical"

This banner is a generic tenancy-limit warning, not the name of the exhausted resource.
Do not assume it means E2.1.Micro is unavailable, and do not upgrade to a paid shape
just to dismiss it.

1. Select **View all limits, quotas and usage** in the warning. If that link does not
   open the page, use **Governance & Administration -> Tenancy Management -> Limits,
   Quotas and Usage**.
2. Confirm the page's region is the same home region where the instance is being
   created.
3. Select **Edit filters** if the filter controls are hidden.
4. Set:
   - **Service:** `Compute`;
   - **Scope:** the availability domain selected for the instance;
   - **Compartment:** `penny-saved-production` (also inspect the tenancy/root scope if
     the page reports limits there); and
   - **Resource:** search for `E2`, `Micro`, or the limit name
     `standard-e2-micro-core-count`.
5. Inspect the row's **Service Limit**, **Usage**, and **Available** values.

Interpret the E2 row as follows:

| What the page shows | What to do |
| --- | --- |
| **Available** is at least enough for one E2.1.Micro instance | Return to the instance form and continue. The generic warning refers to another resource or merely says the account is approaching a limit. |
| **Available** is `0` and an existing E2.1.Micro instance is listed under **Compute -> Instances** | Use the existing instance if appropriate, or terminate it only if you are certain it is disposable and its data is backed up. Do not delete an unfamiliar instance. |
| **Available** is `0`, but there is no existing E2.1.Micro instance | Confirm the correct AD and home region. If they are correct, the tenancy limit/quota blocks creation; request a limit increase through Oracle Support or wait/contact Oracle. |
| A compartment quota is `0` or exhausted while the tenancy service limit has space | An administrator must change the compartment quota; switching shapes does not fix it. |

Also check **Block Volume** limits because every instance creates a boot volume:

1. Change **Service** to **Block Volume**.
2. Inspect total boot/block volume storage and boot-volume counts in the home region.
3. This guide requests one 50 GB boot volume. Oracle documents 200 GB total of Always
   Free boot plus block-volume storage in the home region. Existing volumes—including
   volumes left behind by terminated instances—count against storage usage.

Finally, return to the create-instance page and expand the warning if OCI identifies a
specific limit. Continue only when the E2 Micro row has availability and at least 50 GB
of eligible boot-volume capacity remains. A yellow/critical banner by itself is not a
billing authorization; the selected shape must still say **Always Free eligible**, and
the cost estimate should not show an unexpected compute charge.

Oracle makes E2.1.Micro available in only one availability domain in regions that have
multiple ADs. If OCI changes or restricts **Placement**, accept the AD where
E2.1.Micro is available. Set **Fault domain** to **Let Oracle choose the best fault
domain** or **No preference**. If OCI reports E2 capacity is unavailable even in the
allowed AD, retry later; do not silently select a paid shape.

## 5. Verify and record the ephemeral public IP

After instance creation, OCI displays two different addresses. For example:

```text
Public IPv4 address:  132.145.170.34
Private IPv4 address: 10.0.0.220
```

- `10.0.0.220` is the VM's internal VCN address. Keep it automatically assigned and do
  not put it in GoDaddy DNS.
- `132.145.170.34` is this deployment's current **ephemeral public IP** used for SSH
  and public web traffic. Keep it while it remains assigned to the VM.

A **reserved public IP** is another public IPv4 address allocated by OCI that persists
until you explicitly delete it. It can later be moved to a replacement VM in the same
region, allowing GoDaddy DNS to keep the same address if this VM must be rebuilt.

An **ephemeral public IP** is an internet-facing IPv4 address that OCI temporarily
attaches to this VM's private IP. "Ephemeral" means the address belongs to the current
VM/VNIC assignment rather than being a separately retained address in the account. It
allows a computer on the internet—such as the administrator's Mac or a visitor's web
browser—to reach the VM. The private `10.0.0.x` address works only inside the OCI VCN,
so without a public IP the Mac cannot SSH directly to the VM and GoDaddy cannot direct
public visitors to it.

This deployment uses an ephemeral IP only because OCI rejected creation of a reserved
IP with the `reserved-public-ip-count` service limit. An ephemeral IP provides the same
SSH, HTTP, and HTTPS connectivity while it remains assigned. The tradeoff is lifecycle:

| Address type | What happens |
| --- | --- |
| **Ephemeral public IP** | Remains attached through ordinary VM reboots and stops/starts, but is deleted if the instance, VNIC, or private-IP assignment is terminated. A replacement VM usually receives a different public IP, requiring a GoDaddy A-record update. |
| **Reserved public IP** | Exists independently until explicitly deleted and can be moved to a replacement VM in the same region, allowing DNS to keep the same address. |

"Ephemeral" does not mean the address changes every few minutes or on every reboot. It
means OCI does not promise to retain it after the underlying instance/VNIC is deleted.

### 5.1 Confirm or restore the ephemeral public IP

If the instance details already show an ephemeral **Public IPv4 address**, keep it; do
not delete or replace it. If **Public IPv4 address** says **Not Assigned**—for example,
because a failed reserved-IP attempt removed the original address—restore one:

1. Open **Compute -> Instances -> penny-saved-prod-1 -> Networking -> Attached
   VNICs**.
2. Select `penny-saved-prod-1-vnic`, then open **IP administration**.
3. On the `10.0.0.220 (Primary IP)` row (or the actual private IP shown by OCI), select
   **Actions -> Edit**.
4. Under **Public IP type**, select **Ephemeral public IP**.
5. Enter `penny-saved-prod-ephemeral-ip` if OCI requests a name.
6. Select **Update**, wait for OCI to display a new **Public IPv4 address**, and copy
   that new address.

### 5.2 Verify the ephemeral public IP and finish this step

From Terminal on the Mac, use the private key in `.ssh` and the current public IP:

```bash
ssh -i "/Users/angelahu/.ssh/penny-saved-oci.key" ubuntu@132.145.170.34
```

If SSH works, run `exit` and continue to GoDaddy. From this point forward, use only the
current `132.145.170.34` address in SSH commands and DNS.

A successful SSH login with the new public IP completes this part of the deployment.
It proves all of the following are working together:

- the compute instance is running;
- the primary VNIC has a public IP;
- `penny-saved-public-subnet` routes through the internet gateway;
- the NSG/security-list and local image allow SSH on TCP port 22;
- the administrator's current public IP is allowed by the SSH rule; and
- the private SSH key on the Mac matches the public key installed on Ubuntu.

Before continuing, record `132.145.170.34` as the current ephemeral public IPv4. Run
`exit` to return from the Ubuntu shell to the Mac, then proceed to section 6 and put
this exact public IP in GoDaddy's `@` A record.

Do not terminate the instance or delete its VNIC without first planning a DNS update.
If the VM is rebuilt, OCI normally assigns a different ephemeral IP; update GoDaddy's A
record to the replacement public IP and re-verify HTTPS. An ordinary reboot or
stop/start keeps the ephemeral address while it remains attached to this instance.

If OCI later grants reserved-IP capacity, migration to a reserved address can be
planned separately with a controlled DNS update. It is not required to continue now.

## 6. Point GoDaddy DNS at OCI

Do this after the final public address (reserved when available, otherwise ephemeral)
answers SSH and before requesting TLS.

1. Sign in to GoDaddy, open **Domain Portfolio**, select `stopimpulsebuying.online`, then
   open **DNS**.
2. Before editing anything, create a DNS rollback record on the Mac. This can be:
   - a note in Apple Notes named `stopimpulsebuying.online DNS rollback`;
   - a secure note in a password manager; or
   - a text/Markdown file such as
     `/Users/angelahu/Documents/stopimpulsebuying-online-dns-before-deployment.md`.

   Keep this record outside the `penny-saved` Git repository. DNS values are generally
   public, but the note is operational evidence and does not belong in application
   source control.

   In the note, record the date/time and copy every existing GoDaddy row whose **Name**
   is `@` or `www`. Capture all four displayed fields: **Type**, **Name**, **Data/Value**,
   and **TTL**. Use this template:

   ```text
   Domain: stopimpulsebuying.online
   Recorded at: REPLACE_WITH_DATE_AND_TIME

   BEFORE DEPLOYMENT
   Type: REPLACE_WITH_TYPE
   Name: @
   Data/Value: REPLACE_WITH_OLD_VALUE
   TTL: REPLACE_WITH_OLD_TTL

   Type: REPLACE_WITH_TYPE
   Name: www
   Data/Value: REPLACE_WITH_OLD_VALUE
   TTL: REPLACE_WITH_OLD_TTL
   ```

   Also take a screenshot of the GoDaddy DNS table and save it with the note. If no `@`
   or `www` row exists, write `No existing @ record` or `No existing www record` rather
   than inventing a value.

   This record is the rollback plan: if the new site must be disconnected, recreate the
   previous rows exactly as recorded. Do not change or delete MX, email-related CNAME,
   TXT, DKIM, SPF, or domain-verification records.
3. Add or edit the apex record:

   | Type | Name | Value | TTL |
   | --- | --- | --- | --- |
   | A | `@` | `132.145.170.34` | 600 seconds if offered, otherwise 1 hour |

4. Add or edit `www`:

   | Type | Name | Value | TTL |
   | --- | --- | --- | --- |
   | CNAME | `www` | `@` (or `stopimpulsebuying.online`) | 1 hour |

5. Remove only conflicting website records for `@` or `www`. Do not alter MX, TXT, or
   mail-related CNAME records. GoDaddy may reject a CNAME when another `www` record
   already exists; edit or remove that specific conflict first.
6. Verify from a machine outside OCI:

```bash
dig +short A stopimpulsebuying.online
dig +short CNAME www.stopimpulsebuying.online
dig +short A www.stopimpulsebuying.online
```

Both names must ultimately resolve to the final public IP. GoDaddy says most changes are
visible within an hour but global propagation can take up to 48 hours. DNS maps names
to the VM; it does not provide TLS or open a firewall.

## 7. Patch and secure Ubuntu

SSH to the final public address assigned in section 5.

### Add swap before installing or building

E2.1.Micro has only 1 GB RAM, so this step is required. Confirm the machine has about
1 GB RAM and little or no swap:

```bash
uname -m
free -h
swapon --show
```

`uname -m` should print `x86_64`. Create a 2 GB root-only swap file:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-penny-saved-swap.conf
sudo sysctl --system
free -h
swapon --show
```

The final two commands must show `/swapfile` with approximately 2 GB. Swap prevents an
abrupt out-of-memory kill during installation or a build, but it uses much slower disk
storage and does not turn E2.1.Micro into a high-capacity server. Do not run the setup
twice: first check `swapon --show` and `/etc/fstab` so `/swapfile` is not duplicated.

### Install and update packages

Run:

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

For the recommended image, `uname -m` should be `x86_64`, Python should be 3.12, and
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

### Why the API does not run as `ubuntu`

The API could technically run as `ubuntu`, but it should not. The `ubuntu` account is
an administrator account with `sudo` access. It installs packages, changes firewall and
systemd configuration, deploys releases, and can administer the entire VM. A bug or
security vulnerability in a public API process running as `ubuntu` would therefore
give an attacker a much more powerful starting point.

The `penny-saved` service account follows the **least privilege** principle: give each
process only the permissions needed for its job. This account has no interactive login,
normal home directory, password-based SSH access, or `sudo` permission. It can read the
application and protected production configuration and run FastAPI, but it cannot
administer the operating system.

The production responsibility split is:

```text
ubuntu
  - administrator/deployment user
  - connects through SSH
  - installs packages and releases
  - manages UFW, Nginx, PostgreSQL, and systemd with sudo

penny-saved
  - non-login application service user
  - runs only the FastAPI/Uvicorn backend
  - reads only the application and configuration it needs
  - has no sudo access

www-data
  - Nginx service user
  - serves the built React frontend
  - proxies /api requests to FastAPI on loopback

postgres
  - PostgreSQL operating-system administrator
  - owns the database server files and processes

penny_saved (inside PostgreSQL)
  - database login used by FastAPI
  - owns only the penny_saved application database
  - is not a PostgreSQL superuser
```

The hyphenated `penny-saved` name is a Linux user; the underscored `penny_saved` name is
a PostgreSQL role. They are separate identities. If the API is exploited, the attacker
initially receives the limited permissions of `penny-saved` rather than the
administrator privileges of `ubuntu`. This separation does not prevent every attack,
but it substantially reduces the potential damage.

```bash
sudo adduser --system --group --home /nonexistent --no-create-home penny-saved
sudo usermod --append --groups penny-saved ubuntu
sudo usermod --append --groups penny-saved www-data
sudo install -d -o ubuntu -g penny-saved -m 2775 /srv/penny-saved/releases
sudo install -d -o root -g penny-saved -m 0750 /etc/penny-saved
sudo install -d -o postgres -g postgres -m 0750 /var/backups/penny-saved
```

The `adduser` command is expected to print messages similar to:

```text
The home dir /nonexistent you specified can't be accessed: No such file or directory
Adding system user `penny-saved' ...
Not creating `/nonexistent'.
```

Those are informational messages, not a failure. `/nonexistent` is intentional: the
`penny-saved` account runs the backend service but should not be used for interactive
login or receive a normal home directory. Confirm creation and permissions:

```bash
getent passwd penny-saved
id penny-saved
id ubuntu
id www-data
ls -ld /srv/penny-saved/releases /etc/penny-saved /var/backups/penny-saved
```

`id ubuntu` and `id www-data` should list `penny-saved` among their groups. The current
Ubuntu shell does not automatically receive group memberships added after login, so
reconnect before continuing.

Before closing this session, open a **second Terminal window on the Mac** and verify a
new SSH connection succeeds—this is especially important after changing UFW:

```bash
ssh -i /Users/angelahu/.ssh/penny-saved-oci.key ubuntu@132.145.170.34
```

If the second connection succeeds, type this in the original Ubuntu session:

```bash
exit
```

The prompt should return from something like:

```text
ubuntu@penny-saved-prod-1-vnic:~$
```

to the Mac's local prompt. If the second SSH window is already connected, it is a fresh
login and can be used to continue. Otherwise, reconnect with the same `ssh` command.
In the fresh Ubuntu login, verify the active session has the group:

```bash
id
```

For this instance, the expected output is similar to:

```text
uid=1001(ubuntu) gid=1001(ubuntu) groups=1001(ubuntu),4(adm),24(cdrom),27(sudo),30(dip),101(lxd),110(penny-saved)
```

The numeric group IDs can differ, but the output must include both `sudo` and
`penny-saved`. Seeing `110(penny-saved)` confirms the new login received the service
group membership. The other groups such as `adm`, `cdrom`, `dip`, and `lxd` are normal
for this Ubuntu image.

After the second SSH session connects successfully and `id` includes `penny-saved`, it
is safe to type `exit` in the original SSH window. Keep the second session open and use
it to continue with section 9, **Configure PostgreSQL**. If `penny-saved` is absent,
verify the earlier `usermod` command before continuing. Do not close your only working
SSH session while a second connection still times out.

The set-group-ID directory causes new releases to inherit the `penny-saved` group.
Nginx gets read-only access to the frontend via group membership; the API cannot write
application releases.

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

1. Type only this line and press Enter. Wait for `CREATE ROLE` and the next
   `postgres=#` prompt:

   ```sql
   CREATE ROLE penny_saved LOGIN;
   ```

2. Type only this line and press Enter:

   ```text
   \password penny_saved
   ```

3. Paste the generated password at `Enter new password`, press Enter, paste it again at
   `Enter it again`, and press Enter. Wait until the `postgres=#` prompt returns.
4. Only after the password prompts are finished, type each SQL statement separately,
   pressing Enter and waiting for the success message after each one:

   ```sql
   CREATE DATABASE penny_saved OWNER penny_saved;
   ```

   Expected response: `CREATE DATABASE`.

   ```sql
   REVOKE ALL ON DATABASE penny_saved FROM PUBLIC;
   ```

   Expected response: `REVOKE`.

5. Exit psql:

   ```text
   \q
   ```

Do not paste `\password` and the later SQL statements as one block. `\password` is a
psql meta-command rather than SQL; a multi-line paste can cause it to consume the
following words as extra arguments, producing messages such as `\password: extra
argument "CREATE" ignored` and leaving the database uncreated.

### Recover from `\password: extra argument ... ignored`

If `CREATE ROLE` succeeded, the password prompts completed, and the later connection
test says `database "penny_saved" does not exist`, the role/password are already valid;
only the database and revoke statements were skipped. At the normal Ubuntu shell
prompt—not inside psql—run:

```bash
sudo -u postgres psql --set=ON_ERROR_STOP=1 \
  --command='CREATE DATABASE penny_saved OWNER penny_saved;'
sudo -u postgres psql --set=ON_ERROR_STOP=1 \
  --command='REVOKE ALL ON DATABASE penny_saved FROM PUBLIC;'
```

Expected output:

```text
CREATE DATABASE
REVOKE
```

Do not run `CREATE ROLE penny_saved LOGIN;` again; PostgreSQL will correctly report
that the role already exists. Confirm the database now exists:

```bash
sudo -u postgres psql --list --tuples-only | grep penny_saved
```

Then test TCP/password auth:

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

On E2.1.Micro these commands can take several minutes and may appear quiet while using
swap. Before starting, `swapon --show` must list the 2 GB `/swapfile` created in section
7. In another SSH session, `free -h` can be used to observe memory. Do not run another
build or package upgrade concurrently.

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
`stopimpulsebuying.online`.

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
```

The example service starts two Uvicorn worker processes, which is too aggressive for
the E2.1.Micro 1 GB VM. Open the installed unit:

```bash
sudoedit /etc/systemd/system/penny-saved.service
```

On its `ExecStart=` line, change only:

```text
--workers 2
```

to:

```text
--workers 1
```

Save and exit. This deployment must use one worker. A single worker is sufficient for
the expected one or two simultaneous users and leaves more memory for PostgreSQL,
Nginx, and the operating system.

For either shape, continue with:

```bash
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
    server_name stopimpulsebuying.online www.stopimpulsebuying.online;
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
curl -I http://stopimpulsebuying.online
```

The `rm` removes only Ubuntu's default enabled-site symlink, not application data. If
the curl cannot connect, check DNS, the OCI NSG, the subnet security list, UFW, and
Nginx before continuing.

Install Certbot from its recommended snap distribution and request both names:

```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/local/bin/certbot
sudo certbot certonly --webroot --webroot-path /var/www/letsencrypt \
  --domain stopimpulsebuying.online --domain www.stopimpulsebuying.online \
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
curl --fail --silent --show-error https://stopimpulsebuying.online/api/health
curl --fail --silent --show-error https://stopimpulsebuying.online/api/ready
curl --head http://stopimpulsebuying.online
curl --head https://www.stopimpulsebuying.online
```

Confirm HTTP and `www` redirect to canonical HTTPS. In a private/incognito browser:

1. Open `https://stopimpulsebuying.online` and confirm the certificate is valid.
2. Sign up with a new production test account.
3. Log out and back in.
4. Create, edit, and delete a disposable entry.
5. Confirm a refresh retains the authenticated session.

On the server, confirm only intended public listeners and private app/database ports:

```bash
sudo ss -lntp
curl --fail --silent --show-error http://127.0.0.1:8000/internal/metrics | head
curl --fail --silent --show-error --output /dev/null --write-out '%{http_code}\n' \
  https://stopimpulsebuying.online/internal/metrics
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
| E2.1.Micro build crashes or freezes | confirm the 2 GB swap file is active with `swapon --show`, check `free -h` and disk space, stop other memory-heavy processes, then retry; build the frontend on an AMD64 build machine if necessary |

## Official references

- [OCI creating a VCN manually](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/create_vcn.htm)
- [OCI public-subnet networking scenario](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/scenarioa.htm)
- [OCI internet gateway configuration](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingIGs.htm)
- [OCI creating a compute instance](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm)
- [OCI Always Free resources and E2.1.Micro limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [OCI reserved public IPs](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/reserved-public-ip-create.htm)
- [GoDaddy A-record instructions](https://www.godaddy.com/help/edit-an-a-record-19239)
- [Certbot Nginx instructions](https://certbot.eff.org/instructions?ws=nginx&os=snap)
- [Ubuntu Server web-service documentation](https://documentation.ubuntu.com/server/how-to/web-services/)

Cloud consoles, pricing, available images, and package versions change. This guide was
checked against the linked official documentation on **2026-08-15**. Reconfirm the image,
shape price/free-tier marker, and console labels at deployment time.
