# OKX + Hummingbot Setup Notes

These are the operating assumptions for the MVP.

## Exchange target

- Exchange: OKX
- Connector ID: `okx_perpetual`
- First instrument: `BTC-USDT-SWAP`

## Important operational notes

From Hummingbot public OKX docs, the perp connector uses `okx_perpetual` and Hummingbot expects the OKX account to be configured appropriately before connecting.

Key assumptions to preserve in this MVP:
- use OKX perpetuals only for the first iteration
- start in single-currency margin mode
- confirm there are no orphaned/open positions before connector restarts
- do not enable large leverage; cap in local risk rules first

## Recommended rollout order

1. Configure OKX API key with minimum required permissions
2. Connect Hummingbot to `okx_perpetual`
3. Verify connector/account state manually
4. Run local risk engine against mocked proposals
5. Wire paper/small-size execution only after decision logs look correct

## Credentials

Never commit real keys.
Use local environment variables or secret management only.

Minimum local environment for this repo:
- `HBOT_ACCOUNT_NAME=primary` (or your actual Hummingbot account namespace)
- `OKX_CONNECTOR_ID=okx_perpetual`
- `OKX_SYMBOL=BTC-USDT-SWAP`
- `HBOT_API_URL=http://localhost:8000`
- `HBOT_API_USERNAME=admin`
- `HBOT_API_PASSWORD=admin`

## First symbol policy

Only one symbol for the MVP:
- `BTC-USDT-SWAP`

Expand to ETH only after:
- account sync is stable
- logs are trustworthy
- denial/approval path is tested
