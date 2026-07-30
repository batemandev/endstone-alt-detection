# Alt Detection Plugin for Endstone

A simple alternative account detection system for Minecraft Bedrock servers. Tracks player connections and identifies potential alt accounts through IP addresses, device IDs, and Xbox User IDs.

## Features

- Detects alt accounts using IP addresses, device IDs, and XUIDs
- Tracks player login history and device information
- Real-time notifications to operators when potential alts join
- Subnet analysis for players on the same network
- Simple JSON file storage

## Installation

1. Place the plugin file in your server's `plugins` directory
2. Run the reload command or restart your server
3. Plugin will automatically create necessary files

## Commands

### `/alt-check <target>`
Check for alt accounts by player name or IP address.

```
/alt-check PlayerName
/alt-check 192.168.1.100
```

**Permission:** `altdetection.use` (default: op)

### `/alt-whitelist <add|remove|list> [player_name_or_ip]`
Manage the alt detection whitelist. Whitelisted players and IPs no longer trigger join alerts, but they still show up in `/alt-check` results tagged `(Whitelisted)`. Works from both the console and in-game. Entries can also be edited directly in `alt-detection/whitelist.json`.

```
/alt-whitelist add PlayerName
/alt-whitelist add 192.168.1.100
/alt-whitelist remove PlayerName
/alt-whitelist list
```

**Permission:** `altdetection.whitelist` (default: op)

## Example Output

```
--- Alt Check Results for PlayerName ---
Status: Online
First login: 2 days ago
Last login: 5 minutes ago
Total IPs used: 3

Found 2 accounts with matching IPs:
- AltAccount1 (Shared IPs: 2, Shared Devices: 1)
  Status: Offline
  First login: 1 day ago
  Last login: 3 hours ago
```

## Contact

This is a fun project and I'm open to suggestions!

- Discord: @batemandev
- Email: patrickbatemandeveloper@gmail.com