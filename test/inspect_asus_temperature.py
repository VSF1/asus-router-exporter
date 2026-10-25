import asyncio
import os
from pprint import pprint

from asusrouter import AsusRouter
from asusrouter.modules.data import AsusData



# docker run --rm `
#  -v "${PWD}:/app" `
#  -w /app `
#  --entrypoint python `
#  -e ROUTER_HOST=192.168.10.1 `
#  -e ROUTER_PORT=8443 `
#  -e ROUTER_USE_SSL=true `
#  -e ROUTER_USERNAME=admin `
#  -e ROUTER_PASSWORD='your-router-password' `
#  asus-router-exporter:local `
#  test/inspect_asus_temperature.py

async def main():
    router = AsusRouter(
        hostname=os.environ["ROUTER_HOST"],
        username=os.environ["ROUTER_USERNAME"],
        password=os.environ["ROUTER_PASSWORD"],
        port=int(os.environ.get("ROUTER_PORT", "8443")),
        use_ssl=os.environ.get("ROUTER_USE_SSL", "true").lower() == "true",
    )

    try:
        await router.async_connect()
        temperatures = await router.async_get_data(AsusData.TEMPERATURE)
        sysinfo = await router.async_get_data(AsusData.SYSINFO)
        pprint({"temperatures": temperatures})
        pprint(
            {
                "sysinfo_raw": sysinfo,
                "recognized_load_average_fields": (
                    {
                        period: (
                            sysinfo.get("load_avg", {}).get(int(period))
                            if isinstance(sysinfo.get("load_avg"), dict)
                            else None
                        )
                        for period in ("1", "5", "15")
                    }
                    if isinstance(sysinfo, dict)
                    else None
                ),
            }
        )
    finally:
        await router.async_disconnect()


asyncio.run(main())