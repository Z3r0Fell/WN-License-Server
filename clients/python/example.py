# WatchNexus Python client (example)
# Requires Python 3.9+ and `pip install requests`
from watchnexus_client import WatchNexusClient

client = WatchNexusClient(
    base_url="https://licenses.example.com",   # your VPS URL
    api_key="wnk_REPLACE_ME",                  # from /admin/quickstart
    license_key="WNX-REPLACE_ME",              # the customer's license
)

print("server:", client.health())

# First run
token = client.activate(
    hardware_id="01:23:45:67:89:AB",
    domain="customer.example.com",
    device_name="Marie's MacBook Pro",
)
print("activated:", token["activation_id"])

# Heartbeat (e.g. once an hour)
state = client.validate(token,
                        hardware_id="01:23:45:67:89:AB",
                        domain="customer.example.com")
print("valid:", state["valid"], "mode:", state["mode"])

# When the user uninstalls
client.deactivate(token)
