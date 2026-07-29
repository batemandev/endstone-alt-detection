import ipaddress
import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from endstone.plugin import Plugin
from endstone.event import event_handler, PlayerLoginEvent, PlayerQuitEvent
from endstone.command import Command, CommandSender

FLUSH_PERIOD_TICKS = 6000
SUBNET_MASK = 24


class AltDetection(Plugin):
    api_version = "0.5"
    commands = {
        "alt-check": {
            "description": "Check for alternative accounts",
            "usages": ["/alt-check <target: str>"],
            "permissions": ["altdetection.use"],
        }
    }

    permissions = {
        "altdetection.use": {
            "description": "Allow users to use the alt-check command.",
            "default": "op",
        }
    }

    def on_load(self) -> None:
        self.logger.info("System initialized.")

    def on_enable(self) -> None:
        self.logger.info("System is LIVE!")
        self._lock = threading.Lock()
        self._players_dirty = False
        self._mappings_dirty = False
        self.setup_database()
        self.load_cache()
        self.build_indexes()
        self.register_events(self)
        self._flush_task = self.server.scheduler.run_task(
            self, self.flush_cache, delay=FLUSH_PERIOD_TICKS, period=FLUSH_PERIOD_TICKS
        )

    def on_disable(self) -> None:
        self.flush_cache()
        self.logger.info("System has been shut down.")

    def setup_database(self) -> None:
        self.db_dir = Path("alt-detection")
        self.db_dir.mkdir(exist_ok=True)

        self.players_file = self.db_dir / "players.json"
        self.mappings_file = self.db_dir / "mappings.json"

        if not self.players_file.exists():
            self._atomic_write(self.players_file, {})
            self.logger.info("Created players.json file")

        if not self.mappings_file.exists():
            initial_mappings = {
                "ip_to_players": {},
                "xuid_to_players": {},
                "device_to_players": {}
            }
            self._atomic_write(self.mappings_file, initial_mappings)
            self.logger.info("Created mappings.json file")

    def load_cache(self) -> None:
        self._players = self._read_json(self.players_file, {})

        mappings = self._read_json(self.mappings_file, {})
        mappings.setdefault("ip_to_players", {})
        mappings.setdefault("xuid_to_players", {})
        mappings.setdefault("device_to_players", {})
        self._mappings = mappings

    def _read_json(self, path: Path, default: dict) -> dict:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            self.logger.warning(f"Could not load {path.name}, using default")
            return default

    def _atomic_write(self, path: Path, data: dict) -> None:
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, path)
        except Exception as e:
            self.logger.error(f"Failed to write {path.name}: {e}")
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def flush_cache(self) -> None:
        with self._lock:
            if self._players_dirty:
                self._atomic_write(self.players_file, self._players)
                self._players_dirty = False
            if self._mappings_dirty:
                self._atomic_write(self.mappings_file, self._mappings)
                self._mappings_dirty = False

    def build_indexes(self) -> None:
        self._name_index = {}
        self._subnet_index = {}

        for player_name, info in self._players.items():
            self._name_index[player_name.lower()] = player_name
            for ip_entry in info.get("ips", []):
                ip = ip_entry["ip"] if isinstance(ip_entry, dict) else ip_entry
                self._add_to_subnet_index(player_name, ip)

    def _network_key(self, ip: str, subnet_mask: int = SUBNET_MASK) -> str:
        try:
            return str(ipaddress.IPv4Network(f"{ip}/{subnet_mask}", strict=False).network_address)
        except Exception:
            return None

    def _add_to_subnet_index(self, player_name: str, ip: str) -> None:
        network = self._network_key(ip)
        if network is None:
            return
        self._subnet_index.setdefault(network, set()).add(player_name)

    def find_player_by_name(self, search_name: str) -> str:
        return self._name_index.get(search_name.lower())

    def format_time_ago(self, timestamp_str: str) -> str:
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            now = datetime.now()
            diff = now - timestamp

            total_seconds = int(diff.total_seconds())

            if total_seconds <= 0:
                return "just now"

            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if seconds > 0:
                parts.append(f"{seconds}s")

            if not parts:
                return "just now"

            return " ".join(parts) + " ago"
        except Exception as e:
            self.logger.warning(f"Could not parse timestamp {timestamp_str}: {e}")
            return "unknown time"

    def is_player_online(self, player_name: str) -> bool:
        online_players = [player.name.lower() for player in self.server.online_players]
        return player_name.lower() in online_players

    def get_player_by_ip(self, ip_address: str) -> str:
        for player in self.server.online_players:
            player_ip = str(player.address).split(':')[0]
            if player_ip == ip_address:
                return player.name
        return None

    def get_online_player_info(self, player_name: str) -> dict:
        for player in self.server.online_players:
            if player.name.lower() == player_name.lower():
                return {
                    "device_os": player.device_os,
                    "xuid": player.xuid
                }
        return None

    def get_online_operators(self) -> list:
        operators = []
        for player in self.server.online_players:
            if player.is_op:
                operators.append(player)
        return operators

    def send_toast_to_operators(self, title: str, content: str) -> None:
        operators = self.get_online_operators()
        for operator in operators:
            try:
                operator.send_toast(title, content)
                operator.send_message(f"§c[Alt Detection System] §h{content}. Run /alt-check command for more details")
            except Exception as e:
                self.logger.error(f"Failed to send toast to operator {operator.name}: {e}")

    def check_for_alt_on_join(self, player_name: str) -> dict:
        result = self.find_alts_by_player(player_name)

        if not result["found"]:
            return {"is_alt": False, "related_count": 0}

        related_players = result["related_players"]
        direct_matches = [alt for alt in related_players if alt.get("connection_type") == "direct"]

        return {
            "is_alt": len(direct_matches) > 0,
            "related_count": len(direct_matches),
            "related_players": direct_matches
        }

    def _update_mappings_locked(self, player_name: str, ip_address: str, xuid: str, device_id: str) -> None:
        mappings = self._mappings

        for bucket_name, value in (
            ("ip_to_players", ip_address),
            ("xuid_to_players", xuid),
            ("device_to_players", device_id),
        ):
            bucket = mappings[bucket_name]
            if value not in bucket:
                bucket[value] = []
            if player_name not in bucket[value]:
                bucket[value].append(player_name)

    def update_last_seen(self, player_name: str) -> None:
        with self._lock:
            if player_name in self._players:
                self._players[player_name]["last_seen"] = datetime.now().isoformat()
                self._players_dirty = True
                self.logger.info(f"Updated last_seen for {player_name}")
            else:
                self.logger.warning(f"Attempted to update last_seen for unknown player: {player_name}")

    def log_player_data(self, player_name: str, ip_address: str, xuid: str, device_id: str, device_os: str,
                        game_version: str, locale: str, unique_id: str) -> None:
        current_time = datetime.now().isoformat()

        with self._lock:
            players = self._players

            if player_name not in players:
                players[player_name] = {
                    "ips": [],
                    "xuids": [],
                    "device_ids": [],
                    "device_os": [],
                    "game_versions": [],
                    "locales": [],
                    "unique_ids": [],
                    "first_seen": current_time,
                    "last_seen": current_time
                }
                self._name_index[player_name.lower()] = player_name

            players[player_name]["last_seen"] = current_time

            current_ips = [entry["ip"] if isinstance(entry, dict) else entry for entry in players[player_name]["ips"]]
            if ip_address not in current_ips:
                players[player_name]["ips"].append({"ip": ip_address, "timestamp": current_time})
                self._add_to_subnet_index(player_name, ip_address)
                self.logger.info(f"New IP recorded for {player_name}: {ip_address}")

            current_xuids = [entry["xuid"] if isinstance(entry, dict) else entry for entry in players[player_name]["xuids"]]
            if xuid not in current_xuids:
                players[player_name]["xuids"].append({"xuid": xuid, "timestamp": current_time})
                self.logger.info(f"New XUID recorded for {player_name}: {xuid}")

            current_device_ids = [entry["device_id"] if isinstance(entry, dict) else entry for entry in
                                  players[player_name]["device_ids"]]
            if device_id not in current_device_ids:
                players[player_name]["device_ids"].append({"device_id": device_id, "timestamp": current_time})
                self.logger.info(f"New Device ID recorded for {player_name}: {device_id}")

            current_device_os = [entry["device_os"] if isinstance(entry, dict) else entry for entry in
                                 players[player_name]["device_os"]]
            if device_os not in current_device_os:
                players[player_name]["device_os"].append({"device_os": device_os, "timestamp": current_time})
                self.logger.info(f"New Device OS recorded for {player_name}: {device_os}")

            current_game_versions = [entry["game_version"] if isinstance(entry, dict) else entry for entry in
                                     players[player_name]["game_versions"]]
            if game_version not in current_game_versions:
                players[player_name]["game_versions"].append({"game_version": game_version, "timestamp": current_time})
                self.logger.info(f"New Game Version recorded for {player_name}: {game_version}")

            current_locales = [entry["locale"] if isinstance(entry, dict) else entry for entry in
                               players[player_name]["locales"]]
            if locale not in current_locales:
                players[player_name]["locales"].append({"locale": locale, "timestamp": current_time})
                self.logger.info(f"New Locale recorded for {player_name}: {locale}")

            current_unique_ids = [entry["unique_id"] if isinstance(entry, dict) else entry for entry in
                                  players[player_name]["unique_ids"]]
            if unique_id not in current_unique_ids:
                players[player_name]["unique_ids"].append({"unique_id": unique_id, "timestamp": current_time})
                self.logger.info(f"New Unique ID recorded for {player_name}: {unique_id}")

            self._update_mappings_locked(player_name, ip_address, xuid, device_id)

            self._players_dirty = True
            self._mappings_dirty = True

    def is_ip_address(self, text: str) -> bool:
        ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        return re.match(ip_pattern, text) is not None

    def are_ips_in_same_subnet(self, ip1: str, ip2: str, subnet_mask: int = SUBNET_MASK) -> bool:
        try:
            network1 = ipaddress.IPv4Network(f"{ip1}/{subnet_mask}", strict=False)
            network2 = ipaddress.IPv4Network(f"{ip2}/{subnet_mask}", strict=False)
            return network1.network_address == network2.network_address
        except:
            return False

    def find_alts_by_ip(self, ip_address: str) -> dict:
        with self._lock:
            mappings = self._mappings
            players_data = self._players

            if ip_address not in mappings["ip_to_players"]:
                return {"found": False, "players": []}

            players_with_ip = list(mappings["ip_to_players"][ip_address])
            detailed_players = []

            for player_name in players_with_ip:
                if player_name in players_data:
                    player_info = players_data[player_name]
                    detailed_players.append({
                        "name": player_name,
                        "first_seen": player_info.get("first_seen", "Unknown"),
                        "last_seen": player_info.get("last_seen", "Unknown"),
                        "total_ips": len(player_info.get("ips", [])),
                        "total_devices": len(player_info.get("device_ids", [])),
                        "is_online": self.is_player_online(player_name)
                    })

            return {"found": True, "players": detailed_players}

    def find_alts_by_player(self, player_name: str) -> dict:
        actual_player_name = self.find_player_by_name(player_name)
        if not actual_player_name:
            return {"found": False, "message": f"§cNo data found for player: {player_name}"}

        with self._lock:
            players_data = self._players
            mappings = self._mappings

            player_info = players_data[actual_player_name]
            related_players = set()

            for ip_entry in player_info.get("ips", []):
                ip = ip_entry["ip"] if isinstance(ip_entry, dict) else ip_entry
                related_players.update(mappings["ip_to_players"].get(ip, []))

            for xuid_entry in player_info.get("xuids", []):
                xuid = xuid_entry["xuid"] if isinstance(xuid_entry, dict) else xuid_entry
                related_players.update(mappings["xuid_to_players"].get(xuid, []))

            for device_entry in player_info.get("device_ids", []):
                device_id = device_entry["device_id"] if isinstance(device_entry, dict) else device_entry
                related_players.update(mappings["device_to_players"].get(device_id, []))

            subnet_related = set()
            for ip_entry in player_info.get("ips", []):
                ip = ip_entry["ip"] if isinstance(ip_entry, dict) else ip_entry
                network = self._network_key(ip)
                if network:
                    subnet_related.update(self._subnet_index.get(network, set()))

            related_players.discard(actual_player_name)
            subnet_related.discard(actual_player_name)

            detailed_players = []
            for related_player in related_players:
                if related_player in players_data:
                    related_info = players_data[related_player]
                    detailed_players.append({
                        "name": related_player,
                        "first_seen": related_info.get("first_seen", "Unknown"),
                        "last_seen": related_info.get("last_seen", "Unknown"),
                        "shared_ips": self.count_shared_ips(player_info, related_info),
                        "shared_devices": self.count_shared_devices(player_info, related_info),
                        "connection_type": "direct",
                        "is_online": self.is_player_online(related_player),
                        "xuids": related_info.get("xuids", [])
                    })

            for subnet_player in subnet_related:
                if subnet_player not in related_players and subnet_player in players_data:
                    related_info = players_data[subnet_player]
                    detailed_players.append({
                        "name": subnet_player,
                        "first_seen": related_info.get("first_seen", "Unknown"),
                        "last_seen": related_info.get("last_seen", "Unknown"),
                        "shared_ips": 0,
                        "shared_devices": 0,
                        "connection_type": "subnet",
                        "is_online": self.is_player_online(subnet_player),
                        "xuids": related_info.get("xuids", [])
                    })

            return {
                "found": True,
                "target_player": {
                    "name": actual_player_name,
                    "first_seen": player_info.get("first_seen", "Unknown"),
                    "last_seen": player_info.get("last_seen", "Unknown"),
                    "total_ips": len(player_info.get("ips", [])),
                    "total_devices": len(player_info.get("device_ids", [])),
                    "xuids": player_info.get("xuids", []),
                    "device_os": player_info.get("device_os", []),
                    "is_online": self.is_player_online(actual_player_name)
                },
                "related_players": detailed_players
            }

    def count_shared_ips(self, player1_info: dict, player2_info: dict) -> int:
        player1_ips = {ip["ip"] if isinstance(ip, dict) else ip for ip in player1_info.get("ips", [])}
        player2_ips = {ip["ip"] if isinstance(ip, dict) else ip for ip in player2_info.get("ips", [])}
        return len(player1_ips.intersection(player2_ips))

    def count_shared_devices(self, player1_info: dict, player2_info: dict) -> int:
        player1_devices = {device["device_id"] if isinstance(device, dict) else device for device in
                           player1_info.get("device_ids", [])}
        player2_devices = {device["device_id"] if isinstance(device, dict) else device for device in
                           player2_info.get("device_ids", [])}
        return len(player1_devices.intersection(player2_devices))

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        if command.name == "alt-check":
            return self.handle_alt_check_command(sender, args)
        return False

    def handle_alt_check_command(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) == 0:
            sender.send_error_message("Usage: /alt-check <player_name_or_ip>")
            online_players = [player.name for player in self.server.online_players]
            if online_players:
                sender.send_message(f"§eOnline players: {', '.join(online_players)}")
            return False

        target = " ".join(args)

        if target.startswith('"') and target.endswith('"'):
            target = target[1:-1]
        elif target.startswith("'") and target.endswith("'"):
            target = target[1:-1]

        if self.is_ip_address(target):
            self.check_by_ip(sender, target)
        else:
            self.check_by_player(sender, target)

        return True

    def check_by_ip(self, sender: CommandSender, ip_address: str) -> None:
        result = self.find_alts_by_ip(ip_address)

        online_player = self.get_player_by_ip(ip_address)
        if online_player:
            sender.send_message(f"§aPlayer {online_player} is currently online with this IP!")

        if not result["found"]:
            sender.send_message(f"§7No players found using {ip_address}")
            return

        player_count = len(result['players'])
        player_word = "player" if player_count == 1 else "players"
        sender.send_message(f" ")
        sender.send_message(f"§b--- Alt Check Results for {ip_address} ---")
        sender.send_message(f"§aFound {player_count} {player_word} using this IP:")

        for player in result["players"]:
            online_status = "§aStatus: §hOnline" if player['is_online'] else "§cStatus: §hOffline"
            sender.send_message(
                f"§h- §e{player['name']} §h(IPs: {player['total_ips']}, Devices: {player['total_devices']})")
            sender.send_message(f"  {online_status}")
            sender.send_message(f"  §eFirst login: §h{self.format_time_ago(player['first_seen'])}")
            sender.send_message(f"  §aLast login: §h{self.format_time_ago(player['last_seen'])}")
            sender.send_message(f" ")

    def check_by_player(self, sender: CommandSender, player_name: str) -> None:
        result = self.find_alts_by_player(player_name)

        if not result["found"]:
            sender.send_message(result["message"])
            return

        target = result["target_player"]
        related = result["related_players"]

        sender.send_message(f" ")
        sender.send_message(f"§a--- Alt Check Results for {target['name']} ---")
        online_status = "§aStatus: §hOnline" if target['is_online'] else "§cStatus: §hOffline"
        sender.send_message(f"{online_status}")
        sender.send_message(f"§eFirst login: §h{self.format_time_ago(target['first_seen'])}")
        sender.send_message(f"§aLast login: §h{self.format_time_ago(target['last_seen'])}")
        sender.send_message(f"§vTotal IPs used: §h{target['total_ips']}")
        sender.send_message(f"§cTotal devices used: §h{target['total_devices']}")

        if target['xuids']:
            for xuid_entry in target['xuids']:
                xuid = xuid_entry["xuid"] if isinstance(xuid_entry, dict) else xuid_entry
                sender.send_message(f"§9XUID:§h {xuid}")
                sender.send_message(f" ")

        if target['device_os']:
            sender.send_message("§cDevice OS:")
            for device_os_entry in target['device_os']:
                device_os = device_os_entry["device_os"] if isinstance(device_os_entry, dict) else device_os_entry
                sender.send_message(f"  §h- {device_os}")

        if not related:
            sender.send_message("§aNo alternative accounts detected.")
            return

        direct_matches = [alt for alt in related if alt.get("connection_type") == "direct"]
        subnet_matches = [alt for alt in related if alt.get("connection_type") == "subnet"]

        if direct_matches:
            direct_count = len(direct_matches)
            account_word = "account" if direct_count == 1 else "accounts"
            sender.send_message(f" ")
            sender.send_message(f"§aFound {direct_count} {account_word} with matching IPs:")
            for alt in direct_matches:
                online_status = "§aStatus: §hOnline" if alt['is_online'] else "§cStatus: §hOffline"
                sender.send_message(
                    f"§h- §e{alt['name']} §h(Shared IPs: {alt['shared_ips']}, Shared Devices: {alt['shared_devices']})")
                sender.send_message(f"  {online_status}")
                sender.send_message(f"  §eFirst login: §h{self.format_time_ago(alt['first_seen'])}")
                sender.send_message(f"  §aLast login: §h{self.format_time_ago(alt['last_seen'])}")

                if alt['xuids']:
                    xuid_display = alt['xuids'][0]["xuid"] if isinstance(alt['xuids'][0], dict) else alt['xuids'][0]
                    sender.send_message(f"  §9XUID: §h{xuid_display}")

                if alt['is_online']:
                    online_info = self.get_online_player_info(alt['name'])
                    if online_info:
                        sender.send_message(f"  §cCurrent Device OS: §h{online_info['device_os']}")
                        sender.send_message(f" ")

        if subnet_matches:
            subnet_count = len(subnet_matches)
            account_word = "account" if subnet_count == 1 else "accounts"

            sender.send_message(f" ")
            sender.send_message(f"§aFound {subnet_count} possible alt {account_word} on same network:")
            for alt in subnet_matches:
                online_status = "§aStatus: §hOnline" if alt['is_online'] else "§cStatus: §hOffline"
                sender.send_message(f"§h- §e{alt['name']} §h(Same subnet)")
                sender.send_message(f"  {online_status}")
                sender.send_message(f"  §eFirst login: §h{self.format_time_ago(alt['first_seen'])}")
                sender.send_message(f"  §aLast login: §h{self.format_time_ago(alt['last_seen'])}")

                if alt['xuids']:
                    xuid_display = alt['xuids'][0]["xuid"] if isinstance(alt['xuids'][0], dict) else alt['xuids'][0]
                    sender.send_message(f"  §9XUID: §h{xuid_display}")

                if alt['is_online']:
                    online_info = self.get_online_player_info(alt['name'])
                    if online_info:
                        sender.send_message(f"  §cCurrent Device OS: §h{online_info['device_os']}")
                        sender.send_message(f" ")

    @event_handler
    def on_player_login(self, event: PlayerLoginEvent) -> None:
        player = event.player
        ip_address = str(player.address).split(':')[0]
        xuid = player.xuid
        device_id = player.device_id
        device_os = player.device_os
        game_version = player.game_version
        locale = player.locale
        unique_id = str(player.unique_id)

        self.logger.info(f"Player {player.name} logging in with network {ip_address} on {device_os}")
        self.log_player_data(player.name, ip_address, xuid, device_id, device_os, game_version, locale, unique_id)

        alt_check_result = self.check_for_alt_on_join(player.name)

        if alt_check_result["is_alt"]:
            related_count = alt_check_result["related_count"]
            related_names = [alt["name"] for alt in alt_check_result["related_players"]]

            toast_title = "§cAlt Detection System"

            if related_count == 1:
                toast_content = f"{player.name} may be an alt of {related_names[0]}"
            else:
                toast_content = f"{player.name} linked to {related_count} accounts: {', '.join(related_names[:3])}"
                if related_count > 3:
                    toast_content += f" and {related_count - 3} more"

            self.send_toast_to_operators(toast_title, toast_content)

            self.logger.info(f"{player.name} is linked to {related_count} accounts")

    @event_handler
    def on_player_quit(self, event: PlayerQuitEvent) -> None:
        player = event.player
        self.update_last_seen(player.name)
