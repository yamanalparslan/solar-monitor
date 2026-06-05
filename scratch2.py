import asyncio
from pymodbus.client import AsyncModbusTcpClient

async def test():
    client = AsyncModbusTcpClient("10.35.14.11", port=502, timeout=3.0)
    connected = await client.connect()
    print("Connected:", connected)
    if not connected:
        return
    
    slave_ids = [1, 2, 3]
    addrs = [25, 26, 27, 28, 29, 30, 93, 44, 36]
    
    for slave in slave_ids:
        print(f"\n--- SLAVE {slave} ---")
        for addr in addrs:
            try:
                rr = await client.read_holding_registers(address=addr, count=1, slave=slave)
                if rr.isError():
                    rr_in = await client.read_input_registers(address=addr, count=1, slave=slave)
                    if rr_in.isError():
                        print(f"Addr {addr}: Holding Error ({rr}) | Input Error ({rr_in})")
                    else:
                        print(f"Addr {addr}: Input Success -> {rr_in.registers[0]}")
                else:
                    print(f"Addr {addr}: Holding Success -> {rr.registers[0]}")
            except Exception as e:
                print(f"Addr {addr}: Exception {e}")
            await asyncio.sleep(0.1)

    await client.close()

asyncio.run(test())
