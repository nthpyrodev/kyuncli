# Kyun CLI (Beta)

A command-line interface for using [kyun.sh](https://kyun.sh).  
> **Note:** This project is currently in **beta**.

---

## Installation

> The following assumes you are on Linux. Windows is not supported yet.

### Install from PyPI (Recommended)

Install with pipx:

```bash
sudo apt install pipx
pipx ensurepath
pipx install kyuncli

# Now you can use Kyun CLI
kyun account login

# To upgrade
pipx upgrade kyuncli

# To uninstall
pipx uninstall kyuncli
```

### Install from releases

Use the `.whl` link from [Releases](https://git.kyun.sh/nthpyrodev/kyuncli/-/releases):

```bash
pipx install <link-to-release>
```

### Build it yourself

If you prefer to build the package yourself:

```bash
sudo apt install pipx
pipx ensurepath

git clone https://git.kyun.sh/nthpyrodev/kyuncli.git
cd kyuncli
python3 -m venv .venv
source .venv/bin/activate
pip install build
python -m build
deactivate

# Install your locally built wheel
pipx install dist/kyuncli-*.whl

# Now you can use Kyun CLI
kyun account login

# To uninstall
pipx uninstall kyuncli
```

### Installing in a virtual environment (for development)

```bash
git clone https://git.kyun.sh/nthpyrodev/kyuncli.git
cd kyuncli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Shell Autocompletion (Linux)

Enable tab completion using:

```bash
echo 'eval "$(_KYUN_COMPLETE=bash_source kyun)"' >> ~/.bashrc
source ~/.bashrc
```

## Usage

### Account Management

```bash
# Create a new account
kyun account create

# Login to your account and create the API to use
kyun account login

# Switch between accounts
kyun account switch <hash>

# List all accounts
kyun account list

# Check balance
kyun account balance

# Remove an account (does not delete your account, just removes it locally)
kyun account remove <hash>
```

### SSH Key Management

```bash
# List SSH keys
kyun account ssh list

# Add SSH key from file
kyun account ssh add --file ~/.ssh/id_rsa.pub --name "My Key"

# Add SSH key directly
kyun account ssh add --key "ssh-rsa AAAAB3..." --name "My Key"

# Rename SSH key
kyun account ssh rename <key_id> "New Name"

# Delete SSH key
kyun account ssh delete <key_id>
```

### Contact Information Management

```bash
# Get contact information
kyun account contact get

# Update email address
kyun account contact update --email "your@email.com"

# Update Matrix ID
kyun account contact update --matrix "@user:matrix.org"

# Update both email and Matrix
kyun account contact update --email "your@email.com" --matrix "@user:matrix.org"

# Link Telegram account
kyun account contact telegram link --code "ABC123"

# Unlink Telegram account
kyun account contact telegram unlink
```

### 2FA/OTP Management

```bash
# Check if 2FA is enabled
kyun account otp status

# Enable 2FA (Also creates backup scratch token)
kyun account otp enable

# Disable 2FA
kyun account otp disable
```

### danbo Management

```bash
# List all danbos
kyun danbo list

# Get detailed danbo info
kyun danbo get <danbo_id>

# Buy a new danbo
kyun danbo buy

# Rename a danbo
kyun danbo rename <danbo_id> "New Name"

# View danbo resource usage statistics
kyun danbo stats <danbo_id>

# View stats for last 60 minutes
kyun danbo stats <danbo_id> --minutes 60

# Delete a danbo (Irreversible)
kyun danbo manage delete <danbo_id>

# Cancel a danbo (deleted on next renewal)
kyun danbo manage cancel <danbo_id>

# Cancel a danbo with 2FA code
kyun danbo manage cancel <danbo_id>
```

### danbo Power Management

```bash
# Start a danbo
kyun danbo power start <danbo_id>

# Stop a danbo
kyun danbo power stop <danbo_id>

# Reboot a danbo
kyun danbo power reboot <danbo_id>

# Graceful shutdown
kyun danbo power shutdown <danbo_id>
```

### danbo Specs Management

```bash
# View current specs
kyun danbo get <danbo_id>

# Check max upgrade options
kyun danbo specs max-upgrade <danbo_id>

# Change specs
kyun danbo specs change <danbo_id>
```

### danbo IP Management

```bash
# Show danbo information
kyun danbo get <danbo_id>

# Add IPv4
kyun danbo ip add <danbo_id>

# Remove IPv4
kyun danbo ip remove <danbo_id> <ip_address>

# Set primary IP
kyun danbo ip set-primary-ip <danbo_id> <ip_address>

# List reverse DNS entries for an IP
kyun danbo ip rdns list <danbo_id> <ip_address>

# Add reverse DNS entry
kyun danbo ip rdns add <danbo_id> <ip_address> <domain>

# Remove reverse DNS entry
kyun danbo ip rdns remove <danbo_id> <ip_address> <domain>
```

### danbo SSH Management

```bash
# View authorized keys
kyun danbo ssh get-authorized <danbo_id>

# Set authorized keys from account (Replaces existing)
kyun danbo ssh set-authorized <danbo_id> --from-account

# Set authorized keys from file (Replaces existing)
kyun danbo ssh set-authorized <danbo_id> --file ~/.ssh/authorized_keys

# Add key to authorized keys
kyun danbo ssh add-to-authorized <danbo_id> --key "ssh-rsa AAAAB3..."

# Remove key from authorized keys
kyun danbo ssh remove-from-authorized <danbo_id> --key "ssh-rsa AAAAB3.."

# Get SSH host keys
kyun danbo ssh get-host-keys <danbo_id>
```

### danbo Bandwidth Management

```bash
# Check current bandwidth limit
kyun danbo bandwidth get <danbo_id>

# Set bandwidth limit (--limit flag optional)
kyun danbo bandwidth set <danbo_id> --limit 100

# Clear bandwidth limit
kyun danbo bandwidth clear <danbo_id>
```

### danbo OS Management

```bash
# Install an OS on a danbo
kyun danbo os install <danbo_id>

# Get the installed OS name
kyun danbo os get <danbo_id>

# Set the OS name
kyun danbo os set <danbo_id> "Debian 12 Bookworm"
```

### danbo Subdomain Management

```bash
# List subdomains
kyun danbo subdomains list <danbo_id>

# Create subdomain
kyun danbo subdomains create <danbo_id> --name "subdomain" --domain "kyun.li" --ip "ip_address"

# Delete subdomain
kyun danbo subdomains delete <danbo_id> <subdomain_id>
```

### danbo Brick Management

```bash
# List attached Bricks
kyun danbo bricks list <danbo_id>

# Attach Brick to danbo
kyun danbo bricks attach <danbo_id> <brick_id>

# Detach Brick from danbo
kyun danbo bricks detach <danbo_id> <brick_id>
```

### Brick Storage Management

```bash
# List all Bricks
kyun brick list

# Get Brick details
kyun brick get <brick_id>

# Buy a new Brick
kyun brick buy

# Grow a Brick
kyun brick grow <brick_id>

# Check max growth
kyun brick max-grow <brick_id>

# Delete a Brick (Irreversible)
kyun brick delete <brick_id>

# Unsuspend a Brick
kyun brick unsuspend <brick_id>
```

### Monero Deposit Management

```bash
# View exchange rates
kyun deposit rates

# List pending deposits
kyun deposit pending

# Create new deposit
kyun deposit create

# Get deposit info
kyun deposit get <deposit_id>

# Check deposit status
kyun deposit status <deposit_id>
```

### Stripe Billing Management

```bash
# Add a payment method
kyun stripe addcard

# Don't open in browser automatically
kyun stripe addcard --url-only

# Show QR code
kyun stripe addcard --qr

# Stripe customer portal (general billing including invoices and payment methods)
kyun stripe portal

# Don't open in browser automatically
kyun stripe portal --url-only

# Show QR code
kyun stripe portal --qr
```

### Support Chat

```bash
# List all chats
kyun chat list

# Start new chat
kyun chat start

# Start chat using ultra private mode
kyun chat start --private

# Open live chat session
kyun chat open <chat_id>

# Use commands inside live chat session:
# /help

# Delete chat
kyun chat delete <chat_id>

# Check online staff
kyun chat staff

# Enable ultra private mode
kyun chat privacy enable <chat_id>

# Disable ultra private mode
kyun chat privacy disable <chat_id>
```

### Notifications

```bash

# Use --all to enable/disable for all accounts, or --hash to specify a specific account, otherwise defaults to currently active account.
# Just enabling a notification type will not allow it to run immediately, make sure you have run kyun notify cron install.
# No need to rerun kyun notify cron install after enabling/disabling notification type.

# Notify when a danbo is suspended
kyun notify danbo suspend enable

# Notify if balance is too low at specified hours ahead of a danbo renewal, default is one notification 72 hours in advance
kyun notify danbo renewal enable --hours-before 72 --hours-before 24

# Notify if balance is too low at specified hours ahead of a brick renewal, default is one notification 72 hours in advance
kyun notify brick renewal enable --hours-before 96 --hours-before 36

# Notify when a brick is suspended
kyun notify brick suspend enable

# Notify on new livechat message
kyun notify chat enable

# Change how many hours in advance of insufficient balance for renewal you are notified (replaces previous)
kyun notify danbo renewal hours 72 24

# Change how many hours in advance of insufficient balance for renewal you are notified (replaces previous)
kyun notify brick renewal hours 72

# Show which notification types are set for all accounts added to kyuncli
kyun notify status

# Manually run all enabled notification checks
kyun notify run

# Run notification checks every 5 minutes
kyun notify cron install

# Remove notification check entry from cron
kyun notify cron remove
```

## Configuration

### Config File Location

Account info is stored in a config file:

- **Linux**: `~/.config/kyuncli/config.json`
- **macOS**: `~/Library/Application Support/kyuncli/config.json`