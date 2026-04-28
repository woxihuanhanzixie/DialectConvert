from gradio_client import Client
c = Client('http://127.0.0.1:7860/')
print(c.view_api(all_endpoints=True))
