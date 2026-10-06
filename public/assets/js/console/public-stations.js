import { stationView } from "./stations.js";
import { empty } from "./ui.js";
const host = document.querySelector("#station-page");
stationView(host, { readOnly: true }).catch((error) => {
  host.innerHTML = empty(error.message);
});
