import sys
import requests

# Maltego passes entity value as sys.argv[1] automatically
username = sys.argv[1] if len(sys.argv) > 1 else "nasa"

with open("D:\\TMI\\debug2.txt", "w") as f:
    f.write(f"sys.argv: {sys.argv}")

xml_data = f"""<MaltegoMessage>
<MaltegoTransformRequestMessage>
<Entities>
<Entity Type="maltego.Person">
<Value>{username}</Value>
<Weight>100</Weight>
<AdditionalFields/>
</Entity>
</Entities>
<Limits HardLimit="12" SoftLimit="12"/>
</MaltegoTransformRequestMessage>
</MaltegoMessage>"""

response = requests.post(
    "http://localhost:8080/run/instagram-transform",
    data=xml_data,
    headers={"Content-Type": "application/xml"}
)

sys.stdout.buffer.write(response.content)
sys.stdout.buffer.flush()