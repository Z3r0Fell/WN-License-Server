// Node 18+ example
import { WatchNexusClient } from './watchnexus.js';

const client = new WatchNexusClient({
  baseUrl: 'https://licenses.example.com',  // your VPS URL
  apiKey:  'wnk_REPLACE_ME',                // from /admin/quickstart
  licenseKey: 'WNX-REPLACE_ME',             // the customer's license
});

console.log('server:', await client.health());

const token = await client.activate({
  hardware_id: '01:23:45:67:89:AB',
  domain: 'customer.example.com',
  device_name: "Marie's MacBook Pro",
});
console.log('activated:', token.activation_id);

const state = await client.validate(token, {
  hardware_id: '01:23:45:67:89:AB',
  domain: 'customer.example.com',
});
console.log('valid:', state.valid, 'mode:', state.mode);

await client.deactivate(token);
