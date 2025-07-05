# Alt Detection Plugin for Endstone

A comprehensive alternative account detection system for Minecraft Bedrock servers using the Endstone plugin framework. This plugin tracks player connections and identifies potential alternative accounts through IP addresses, device IDs, and Xbox User IDs (XUIDs).

## Features

### 🔍 Multi-Vector Detection
- **IP Address Tracking**: Identifies players using the same IP address
- **Device ID Matching**: Detects accounts from the same device
- **XUID Correlation**: Cross-references Xbox User IDs
- **Subnet Analysis**: Finds potential alts on the same network (configurable /24 subnet)

### 📊 Comprehensive Player Data
- First and last login timestamps
- Device OS information
- Game version tracking
- Locale detection
- Complete connection history

### 🚨 Real-time Notifications
- Automatic toast notifications to online operators when potential alts join
- Instant alerts with player correlation details
- Chat notifications for enhanced visibility

### 💾 Persistent Data Storage
- JSON-based database system
- Automatic data backup and recovery
- Efficient mapping system for quick lookups

## Installation

1. Ensure you have Endstone server running
2. Download the plugin file
3. Place it in your server's `plugins` directory
4. Restart your server

## Commands

### `/alt-check <target>`
Check for alternative accounts associated with a player or IP address.

**Usage Examples:**
```
/alt-check PlayerName
/alt-check 192.168.1.100
```

**Permission:** `altdetection.use` (default: op)

## How It Works

### Data Collection
The plugin automatically collects the following data when players join:
- IP Address
- Xbox User ID (XUID)
- Device ID
- Device OS
- Game Version
- Locale
- Unique Player ID

### Detection Methods

1. **Direct Matching**: Players sharing identical IP addresses, device IDs, or XUIDs
2. **Subnet Analysis**: Players connecting from the same network subnet
3. **Historical Correlation**: Cross-referencing past connection data

### Real-time Monitoring
When a player joins, the system:
1. Logs their connection data
2. Analyzes for potential alt accounts
3. Notifies operators if matches are found
4. Updates the player's last seen timestamp

## Output Examples

### Player Check Results
```
--- Alt Check Results for PlayerName ---
Status: Online
First login: 2 days ago
Last login: 5 minutes ago
Total IPs used: 3
Total devices used: 1
XUID: 1234567890123456

Found 2 accounts with matching IPs:
- AltAccount1 (Shared IPs: 2, Shared Devices: 1)
  Status: Offline
  First login: 1 day ago
  Last login: 3 hours ago
  XUID: 9876543210987654
```

### IP Address Check Results
```
--- Alt Check Results for 192.168.1.100 ---
Found 3 players using this IP:
- PlayerName (IPs: 2, Devices: 1)
  Status: Online
  First login: 5 days ago
  Last login: just now
```

## File Structure

The plugin creates the following files in the `alt-detection/` directory:

- `players.json` - Complete player data and connection history
- `mappings.json` - Quick lookup mappings for IP/XUID/Device correlations

## Configuration

The plugin works out of the box with sensible defaults:
- Subnet mask: /24 (configurable in code)
- Automatic data persistence
- Operator-level permissions required

## Technical Details

### Requirements
- Endstone API version 0.5+
- Python 3.7+
- JSON file system access

### Performance
- Efficient lookup algorithms
- Minimal server impact
- Automatic data cleanup and organization

## Privacy & Ethics

This plugin is designed for server administration purposes only. It:
- Only tracks publicly available connection data
- Stores data locally on your server
- Provides tools for legitimate server management
- Respects player privacy within the game environment

## Contributing

This is a fun project and I'm open to suggestions and improvements!

### Found a Bug?
- Discord: @batemandev
- Email: patrickbatemandeveloper@gmail.com

### Want to Contribute?
- Submit issues and feature requests
- Pull requests are welcome
- Share your ideas and improvements

## Changelog

### Version 1.0
- Initial release
- Basic alt detection functionality
- IP, XUID, and device ID tracking
- Real-time operator notifications
- JSON-based data storage

---

**Note**: This plugin is developed for fun and server administration purposes. Please use responsibly and in accordance with your server's terms of service and local regulations.