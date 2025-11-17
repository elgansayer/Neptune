---
applyTo: '**'
---
launching the game to monitor server logs for any errors or warnings related to AI behavior.

Need to use this command in a terminal that supports clearing the screen for better readability.

```sh
clear && echo "time" > server.log && clear && ./bomberman both

tail -f server.log
```

use timeout to limit the duration of the test run:

```sh
timeout 300s bash -c 'clear && echo "time" > server.log && clear && ./bomberman both; tail -f server.log'
```

If you run just the server. You also need to run a client.

```sh
clear && echo "time" > server.log && clear && ./bomberman server & ./bomberman client
```tail -f server.log
``` 

but alwyas use timeout to avoid infinite runs:

```sh
timeout 300s bash -c 'clear && echo "time" > server.log && clear && ./bomberman server & ./bomberman client; tail -f server.log'
``` 