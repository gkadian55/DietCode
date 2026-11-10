# DietCode VS Code Extension

This initial Path B integration sends the current editor selection to the local
DietCode engine and displays the generated result in a VS Code output channel.

Commands:

- `DietCode: Send Selection`
- `DietCode: Open Dashboard`

The extension expects the DietCode backend at `http://127.0.0.1:8765`. Change
`dietcode.backendUrl` in VS Code settings if the backend uses another address.
