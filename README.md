# Kyun CLI (Beta)

A **command-line interface** for using [kyun.host](https://kyun.host).  
> **Note:** This project is currently in **beta**. OS installation, Stripe payments, and account creation are not yet supported.

---

## Installation

```bash
git clone https://git.kyun.host/nthpyrodev/kyuncli.git
cd kyuncli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Dependencies

The project requires Python 3.10+ and the following dependencies:

- `click`
- `httpx`
- `requests`
- `qrcode`
- `python-dotenv`

### Before You Use

- Until account creation functionality is added, create an account at Kyun.host before using this CLI.

## Usage

### Account Management

```bash
# Login to your account to create the API to use
kyun account setup

# Switch between accounts
kyun account login <hash>

# List all accounts
kyun account list

# Check balance
kyun account balance

# Remove an account
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

### Danbo Management

```bash
# List all Danbos
kyun danbo list

# Get detailed Danbo info
kyun danbo get <danbo_id>

# Buy a new Danbo
kyun danbo buy

# Rename a Danbo
kyun danbo rename <danbo_id> "New Name"

# Delete a Danbo (Irreversible)
kyun danbo management delete <danbo_id>

# Cancel a Danbo (deleted on next renewal)
kyun danbo management cancel <danbo_id>
```

### Danbo Power Management

```bash
# Start a Danbo
kyun danbo power start <danbo_id>

# Stop a Danbo
kyun danbo power stop <danbo_id>

# Reboot a Danbo
kyun danbo power reboot <danbo_id>

# Graceful shutdown
kyun danbo power shutdown <danbo_id>
```

### Danbo Specs Management

```bash
# View current specs
kyun danbo get <danbo_id>

# Check max upgrade options
kyun danbo specs max-upgrade <danbo_id>

# Change specs
kyun danbo specs change <danbo_id>
```

### Danbo IP Management

```bash
# Show danbo information
kyun danbo get <danbo_id>

# Add IPv4
kyun danbo ip add <danbo_id>

# Remove IPv4
kyun danbo ip remove <danbo_id> <ip_address>

# Set primary IP
kyun danbo ip set-primary-ip <danbo_id> <ip_address>
```

### Danbo SSH Management

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

### Danbo Bandwidth Management

```bash
# Check current bandwidth limit
kyun danbo bandwidth get <danbo_id>

# Set bandwidth limit (--limit flag optional)
kyun danbo bandwidth set <danbo_id> --limit 100

# Clear bandwidth limit
kyun danbo bandwidth clear <danbo_id>
```

### Danbo Subdomain Management

```bash
# List subdomains
kyun danbo subdomains list <danbo_id>

# Create subdomain
kyun danbo subdomains create <danbo_id> --name "subdomain" --domain "kyun.li" --ip "ip_address"

# Delete subdomain
kyun danbo subdomains delete <danbo_id> <subdomain_id>
```

### Danbo Brick Management

```bash
# List attached Bricks
kyun danbo bricks list <danbo_id>

# Attach Brick to Danbo
kyun danbo bricks attach <danbo_id> <brick_id>

# Detach Brick from Danbo
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

### Deposit Management

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

### Support Chat

```bash
# List all chats
kyun chat list

# Create new chat
kyun chat create

# Create chat using ultra private mode
kyun chat create --private

# View chat messages
kyun chat open <chat_id>

# Delete chat
kyun chat delete <chat_id>

# Check online staff
kyun chat staff

# Enable ultra private mode
kyun chat privacy enable <chat_id>

# Disable ultra private mode
kyun chat privacy disable <chat_id>
```

## Configuration

Account information is stored in `~/.config/kyuncli/config.json`. This includes:

- Account hash
- API key
- User ID

## Development

### Contributing

1. Open an issue first
2. Fork the repository
3. Create a branch
4. Make your changes
5. Submit a pull request

## TODO

- [ ] Add support for installing OS to danbo
- [ ] Store API in keyring
- [ ] Add Stripe support
- [ ] Add serial access
- [ ] Allow sending chat messages
- [ ] Allow fetching of danbo usage stats like cpu, ram, network

## License

This project is licensed under the MIT License, see the LICENSE file for details.
