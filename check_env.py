import os
print("Environment Variables:")
for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"]:
    print(f"{key}: {os.environ.get(key)}")
