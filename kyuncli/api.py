import httpx
import requests

API_BASE = "https://api.kyun.host"

class KyunAPI:
    def __init__(self, api_key: str | None = None, temp_token: str | None = None, otp: str | None = None):
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["X-Auth-Token"] = api_key
        elif temp_token:
            self.headers["X-Auth-Token"] = temp_token
        if otp:
            self.headers["X-OTP-Code"] = otp

        self.client = httpx.Client(base_url=API_BASE, headers=self.headers, timeout=httpx.Timeout(connect=20.0, read=20.0, write=10.0, pool=5.0))

    def get_pow_challenge(self):
        resp = self.client.get("/etc/powChallenge")
        resp.raise_for_status()
        return resp.json()

    def create_account(self, password: str, challenge: str, signature: str, proof: str) -> str:
        payload = {"password": password, "pow": {"challenge": challenge, "signature": signature, "proof": proof}}
        resp = self.client.put("/user", json=payload)
        resp.raise_for_status()
        token = resp.text.strip('"')
        temp_api = KyunAPI(temp_token=token)
        user_info = temp_api.get_user_info()
        return user_info["accountHash"]

    def login(self, hash_: str, password: str, otp: str | None = None) -> str:
        headers = self.headers.copy()
        if otp and otp.strip():
            headers["X-OTP-Code"] = otp.strip()
        resp = self.client.post("/user/logIn", json={"hash": hash_, "password": password}, headers=headers)
        if not resp.is_success:
            raise Exception(f"{resp.status_code}:{resp.text}")
        return resp.text.strip('"')

    def get_user_info(self):
        resp = self.client.get("/user")
        resp.raise_for_status()
        return resp.json()

    def create_api_key(self, label: str) -> str:
        resp = self.client.put("/user/apiKeys", json={"label": label})
        resp.raise_for_status()
        return resp.text.strip('"')

    def get_api_keys(self):
        resp = self.client.get("/user/apiKeys")
        resp.raise_for_status()
        return resp.json()

    def delete_api_key(self, key_id: str):
        resp = self.client.delete(f"/user/apiKeys/{key_id}")
        resp.raise_for_status()
        return resp.status_code

    def get_user_ssh_keys(self):
        resp = self.client.get("/user/sshKeys")
        resp.raise_for_status()
        return resp.json()

    def add_user_ssh_key(self, key: str, name: str | None = None):
        payload = {"key": key}
        if name:
            payload["name"] = name
        resp = self.client.put("/user/sshKeys", json=payload)
        resp.raise_for_status()
        return resp.text.strip('"')

    def rename_user_ssh_key(self, key_id: str, new_name: str):
        resp = self.client.patch(f"/user/sshKeys/{key_id}", json=new_name)
        resp.raise_for_status()
        return resp.status_code

    def delete_user_ssh_key(self, key_id: str):
        resp = self.client.delete(f"/user/sshKeys/{key_id}")
        resp.raise_for_status()
        return resp.status_code

    def get_user_contact(self):
        resp = self.client.get("/user/contact")
        resp.raise_for_status()
        return resp.json()

    def update_user_contact(self, email: str | None = None, matrix: str | None = None):
        payload = {}
        if email is not None:
            payload["email"] = email
        if matrix is not None:
            payload["matrix"] = matrix
        resp = self.client.patch("/user/contact", json=payload)
        resp.raise_for_status()
        return resp.status_code

    def link_telegram(self, code: str):
        resp = self.client.put("/user/contact/telegram", json=code)
        resp.raise_for_status()
        return resp.status_code

    def unlink_telegram(self):
        resp = self.client.delete("/user/contact/telegram")
        resp.raise_for_status()
        return resp.status_code

    def get_deposit_rates(self):
        resp = self.client.get("/deposits/rates")
        resp.raise_for_status()
        return resp.json()

    def get_pending_deposits(self):
        resp = self.client.get("/deposits/pending")
        resp.raise_for_status()
        return resp.json()

    def create_deposit(self, amount: float, currency: str):
        resp = self.client.put("/deposits", json={"amount": amount, "currency": currency})
        resp.raise_for_status()
        return resp.text.strip('"')

    def get_deposit(self, deposit_id: str):
        resp = self.client.get(f"/deposits/{deposit_id}")
        resp.raise_for_status()
        return resp.json()

    def get_deposit_status(self, deposit_id: str):
        resp = self.client.get(f"/deposits/{deposit_id}/status")
        resp.raise_for_status()
        return resp.json()

    def get_owned_danbos(self):
        resp = self.client.get("/services/danbo")
        resp.raise_for_status()
        return resp.json()

    def get_danbo(self, danbo_id: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}")
        resp.raise_for_status()
        return resp.json()

    def get_danbo_specs(self, danbo_id: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}/specs")
        resp.raise_for_status()
        return resp.json()

    def get_danbo_ips(self, danbo_id: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}/ips")
        resp.raise_for_status()
        return resp.json()

    def get_danbo_reverse_dns(self, danbo_id: str, ip: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}/ips/{ip}/reverse")
        resp.raise_for_status()
        return resp.json()

    def add_danbo_reverse_dns(self, danbo_id: str, ip: str, domain: str):
        resp = self.client.put(f"/services/danbo/{danbo_id}/ips/{ip}/reverse", json=domain)
        resp.raise_for_status()
        return resp.status_code

    def remove_danbo_reverse_dns(self, danbo_id: str, ip: str, domain: str):
        resp = self.client.request("DELETE", f"/services/danbo/{danbo_id}/ips/{ip}/reverse", json=domain)
        resp.raise_for_status()
        return resp.status_code

    def get_danbo_ipv6_subnet(self, danbo_id: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}/ips/sixSubnet")
        resp.raise_for_status()
        return resp.text.strip('"')

    def get_danbo_subdomains(self, danbo_id: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}/subdomains")
        resp.raise_for_status()
        return resp.json()

    def get_danbo_bricks(self, danbo_id: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}/bricks/")
        resp.raise_for_status()
        return resp.json()

    def add_danbo_ip(self, danbo_id: str):
        resp = self.client.put(f"/services/danbo/{danbo_id}/ips")
        resp.raise_for_status()
        return resp.status_code
    

    def remove_danbo_ip(self, danbo_id: str, ip: str):
        resp = self.client.delete(f"/services/danbo/{danbo_id}/ips/{ip}")
        resp.raise_for_status()
        return resp.status_code
    
    def set_danbo_primary_ip(self, danbo_id: str, ip: str) -> bool:
        resp = self.client.post(f"/services/danbo/{danbo_id}/ips/{ip}/primary")
        resp.raise_for_status()
        return resp.status_code == 200

    def get_danbo_max_upgrade(self, danbo_id: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}/maxUpgrade")
        resp.raise_for_status()
        return resp.json()

    def change_danbo_specs(self, danbo_id: str, cores: int, ram: float, disk: int):
        data = {"cores": cores, "ram": ram, "disk": disk}
        resp = self.client.patch(f"/services/danbo/{danbo_id}/specs", json=data)
        resp.raise_for_status()
        return resp.status_code

    
    def get_datacenter_prices(self, datacenter_id: str):
        resp = self.client.get(f"/datacenters/{datacenter_id}/prices")
        resp.raise_for_status()
        return resp.json()
    
    def get_datacenter_available_specs(self, datacenter_id: str, cores: int = None, ram: float = None, disk: int = None):
        params = {}
        if cores is not None:
            params["cores"] = str(cores)
        if ram is not None:
            params["ram"] = str(ram)
        if disk is not None:
            params["disk"] = str(disk)
        
        resp = self.client.get(f"/datacenters/{datacenter_id}/availableSpecs", params=params)
        resp.raise_for_status()
        return resp.json()
    
    def change_danbo_power(self, danbo_id: str, action: str):
        resp = self.client.post(f"/services/danbo/{danbo_id}/power", json=action)
        resp.raise_for_status()
        return resp.status_code


    def create_danbo_subdomain(self, danbo_id: str, name: str, domain: str, ip: str):
        payload = {"name": name, "domain": domain, "ip": ip}
        resp = self.client.put(f"/services/danbo/{danbo_id}/subdomains", json=payload)
        resp.raise_for_status()
        return resp.status_code == 200

    def delete_danbo_subdomain(self, danbo_id: str, subdomain_id: str):
        resp = self.client.delete(f"/services/danbo/{danbo_id}/subdomains/{subdomain_id}")
        resp.raise_for_status()
        return resp.status_code == 200

    def get_danbo_bandwidth_limit(self, danbo_id: str) -> float:
        resp = self.client.get(f"/services/danbo/{danbo_id}/bwLimit")
        resp.raise_for_status()
        return resp.json()

    def set_danbo_bandwidth_limit(self, danbo_id: str, limit: float) -> bool:
        payload = {"limit": limit}
        resp = self.client.patch(
            f"/services/danbo/{danbo_id}/bwLimit",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        resp.raise_for_status()
        return resp.status_code == 200

    def clear_danbo_bandwidth_limit(self, danbo_id: str) -> bool:
        resp = self.client.delete(f"/services/danbo/{danbo_id}/bwLimit")
        resp.raise_for_status()
        return resp.status_code == 200

    def get_danbo_authorized_keys(self, danbo_id: str) -> str:
        resp = self.client.get(f"/services/danbo/{danbo_id}/authorizedKeys")
        resp.raise_for_status()
        return resp.text.strip('"')

    def set_danbo_authorized_keys(self, danbo_id: str, keys: str) -> bool:
        resp = self.client.put(f"/services/danbo/{danbo_id}/authorizedKeys", json=keys)
        resp.raise_for_status()
        return resp.status_code == 200

    def get_danbo_host_keys(self, danbo_id: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}/hostKeys")
        resp.raise_for_status()
        return resp.json()

    def get_owned_bricks(self):
        resp = self.client.get("/services/bricks")
        resp.raise_for_status()
        return resp.json()

    def buy_brick(self, gb: int, datacenter: str):
        resp = self.client.put("/services/bricks", json={"gb": gb, "datacenter": datacenter})
        resp.raise_for_status()
        return resp.text.strip('"')

    def get_brick(self, brick_id: str):
        resp = self.client.get(f"/services/bricks/{brick_id}")
        resp.raise_for_status()
        return resp.json()

    def delete_brick(self, brick_id: str, otp: str | None):
        headers = {k: v for k, v in self.headers.items() if k != "Content-Type"}
        if otp:
            headers["X-OTP-Code"] = otp
        resp = requests.delete(f"{API_BASE}/services/bricks/{brick_id}", 
                              headers=headers,
                              json="DELETE BRICK AND ALL DATA NOW, NO UNDO")
        resp.raise_for_status()
        return resp.status_code
    
    def get_brick_max_stock(self, datacenter_id: str):
        resp = self.client.get(f"/datacenters/{datacenter_id}/brickCapacity")
        resp.raise_for_status()
        return resp.json()

    def get_brick_max_grow(self, brick_id: str):
        resp = self.client.get(f"/services/bricks/{brick_id}/maxGrow")
        resp.raise_for_status()
        return resp.json()

    def grow_brick(self, brick_id: str, add_gb: int):
        resp = self.client.post(f"/services/bricks/{brick_id}/grow", json={"addGb": add_gb})
        resp.raise_for_status()
        return resp.status_code


    def pay_to_unsuspend_brick(self, brick_id: str):
        resp = self.client.post(f"/services/bricks/{brick_id}/payToUnsuspend")
        resp.raise_for_status()
        return resp.status_code

    def attach_brick_to_danbo(self, danbo_id: str, brick_id: str):
        resp = self.client.put(f"/services/danbo/{danbo_id}/bricks/{brick_id}")
        resp.raise_for_status()
        return resp.status_code

    def detach_brick_from_danbo(self, danbo_id: str, brick_id: str):
        resp = self.client.delete(f"/services/danbo/{danbo_id}/bricks/{brick_id}")
        resp.raise_for_status()
        return resp.status_code

    def buy_danbo(self, datacenter: str, cores: int, ram: float, disk: int, fours: int = 0):
        payload = {
            "datacenter": datacenter,
            "specs": {"cores": cores, "ram": ram, "disk": disk},
            "fours": fours
        }
        resp = self.client.put("/services/danbo", json=payload)
        resp.raise_for_status()
        return resp.text.strip('"')

    def delete_danbo(self, danbo_id: str, otp: str | None):
        headers = {k: v for k, v in self.headers.items() if k != "Content-Type"}
        if otp:
            headers["X-OTP-Code"] = otp
        resp = requests.delete(f"{API_BASE}/services/danbo/{danbo_id}", 
                              headers=headers,
                              json="DELETE VM AND ALL DATA NOW, NO UNDO")
        resp.raise_for_status()
        return resp.status_code

    def cancel_danbo(self, danbo_id: str, otp: str | None = None):
        headers = {k: v for k, v in self.headers.items()}
        if otp:
            headers["X-OTP-Code"] = otp
        resp = requests.post(f"{API_BASE}/services/danbo/{danbo_id}/billing/cancel", headers=headers)
        resp.raise_for_status()
        return resp.status_code

    def resume_danbo(self, danbo_id: str):
        resp = self.client.post(f"/services/danbo/{danbo_id}/billing/resume")
        resp.raise_for_status()
        return resp.status_code

    def pay_to_unsuspend_danbo(self, danbo_id: str):
        resp = self.client.post(f"/services/danbo/{danbo_id}/billing/payToUnsuspend")
        resp.raise_for_status()
        return resp.status_code

    def rename_danbo(self, danbo_id: str, new_name: str):
        resp = self.client.patch(f"/services/danbo/{danbo_id}/name", json=new_name)
        resp.raise_for_status()
        return resp.status_code

    def get_chats(self):
        resp = self.client.get("/chats")
        resp.raise_for_status()
        return resp.json()

    def create_chat(self, ultra_private_mode: bool = False):
        resp = self.client.put("/chats", json={"ultraPrivateMode": ultra_private_mode})
        resp.raise_for_status()
        return resp.text.strip('"')

    def get_chat_messages(self, chat_id: str):
        resp = self.client.get(f"/chats/{chat_id}/messages")
        resp.raise_for_status()
        return resp.json()


    def mark_chat_read(self, chat_id: str):
        resp = self.client.post(f"/chats/{chat_id}/read")
        resp.raise_for_status()
        return resp.status_code

    def delete_chat(self, chat_id: str):
        resp = self.client.delete(f"/chats/{chat_id}")
        resp.raise_for_status()
        return resp.status_code

    def get_active_staff_count(self):
        resp = self.client.get("/chats/activeStaff")
        resp.raise_for_status()
        return resp.json()

    def enable_ultra_private_mode(self, chat_id: str):
        resp = self.client.post(f"/chats/{chat_id}/enableUltraPrivateMode")
        resp.raise_for_status()
        return resp.status_code

    def disable_ultra_private_mode(self, chat_id: str):
        resp = self.client.post(f"/chats/{chat_id}/disableUltraPrivateMode")
        resp.raise_for_status()
        return resp.status_code

    def get_otp_status(self):
        resp = self.client.get("/user/otp")
        resp.raise_for_status()
        return resp.json()

    def enable_otp(self, secret: str, code: str, scratch_token: str):
        payload = {"secret": secret, "code": code, "scratchToken": scratch_token}
        resp = self.client.put("/user/otp", json=payload)
        resp.raise_for_status()
        return resp.status_code

    def disable_otp(self, otp_code: str):
        headers = self.headers.copy()
        headers["X-OTP-Code"] = otp_code
        resp = self.client.delete("/user/otp", headers=headers)
        resp.raise_for_status()
        return resp.status_code

    def get_danbo_stats(self, danbo_id: str):
        resp = self.client.get(f"/services/danbo/{danbo_id}/stats")
        resp.raise_for_status()
        return resp.json()

    def submit_cloudinit_task(self, node_hostname: str, agent_token: str, os_name: str, image_url: str, checksum: dict | None, authorized_keys: str) -> bool:
        try:
            base_url = f"https://{node_hostname}:1337"
            url = f"{base_url}/guest/cloudInit?token={agent_token}"
            
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "osName": os_name,
                "imageUrl": image_url,
                "authorizedKeys": authorized_keys
            }
            
            if checksum:
                payload["checksum"] = checksum
            
            with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            raise Exception(f"Node agent returned error {e.response.status_code}: {e.response.text}")
        except httpx.TimeoutException:
            raise Exception("TIMEOUT")
        except Exception as e:
            raise Exception(f"Failed to submit cloudInit task to node agent: {e}")

    def get_agent_token(self, danbo_id: str, otp: str | None = None) -> str:
        headers = self.headers.copy()
        if otp:
            headers["X-OTP-Code"] = otp
        resp = self.client.get(f"/services/danbo/{danbo_id}/agentToken", headers=headers)
        resp.raise_for_status()
        return resp.text.strip('"')

    def get_danbo_os_name(self, danbo_id: str) -> str:
        resp = self.client.get(f"/services/danbo/{danbo_id}/osName")
        resp.raise_for_status()
        return resp.text.strip('"')

    def set_danbo_os_name(self, danbo_id: str, os_name: str):
        resp = self.client.patch(f"/services/danbo/{danbo_id}/osName", json=os_name)
        resp.raise_for_status()
        return resp.status_code

    def fetch_os_images_metadata(self) -> dict:
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)) as client:
                resp = client.get("https://mirror.kyun.network/images/meta.json")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            raise Exception(f"Failed to fetch OS images metadata: {e}")
