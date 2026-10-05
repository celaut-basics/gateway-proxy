# gateway-proxy

A TCP splice packaged as a [Celaut](https://github.com/celaut-project/nodo) service.
Each accepted connection is a byte pipe to a gateway. The process has no
protocol awareness, so the same binary fronts plaintext gRPC or TLS.

It exists to **expose a node through a service slot**. `ServiceTunnel` already
reaches a *service* without publishing a port. This reaches a *node*. The
gateway of a peer that does not publish itself (`DISABLE_EXPOSE_OUTSIDE`, NAT)
becomes the declared slot of an instance you launched there. You can then
tunnel that slot through your own node, or advertise it as another URI for
that peer.

One instance per peer is the intended shape.

This is not `ServiceTunnel`. `ServiceTunnel` is `token + slot` to an instance.
This is `host:port` to a `Gateway` RPC.

## What it forwards to

In order, each one winning outright if it is set:

| | where |
|---|---|
| `TARGET=host:port` | a complete override -- typically *our* gateway, when the instance is running on a peer |
| `TARGET_HOST` / `TARGET_PORT` | either piece, the other falling back to `__config__.gateway` |
| `__config__.gateway` | the host node's plaintext gateway, which a service is always allowed to reach |

`LISTEN_PORT` defaults to **4040**, the same number the slot declares.
Keep it at 4040 unless you also change `api[].port`. A different listen
port is not the declared slot, so `nodo tunnel <instance> 4040` misses it.

`nodo execute` passes those names with `-e`. The packer does not record the
`envs` list in `service.json`. The names still work as launch-time variables.

```bash
# Pack, then run. execute may pick this node or a peer.
nodo pack .
nodo execute gateway-proxy

# Front *our* gateway from the instance (often after a run on a peer).
nodo execute -e TARGET 203.0.113.10:4040 gateway-proxy

# Same host, TLS port instead of the plaintext one __config__ names.
nodo execute -e TARGET_PORT 443 gateway-proxy

# Pin the run to one peer (no balancer). Testing and development only.
nodo force_execution <peer-id> gateway-proxy

# Reach the slot from this host. execute prints a local address only.
nodo tunnel <instance> 4040
nodo kill <instance>
```

`nodo execute --remote` was removed. Do not pass it.

`__config__.gateway` is the **plaintext** port (what a service speaks). Other
nodes speak TLS to `GATEWAY_PORT`. If the clients of this instance speak TLS,
pass `TARGET` / `TARGET_PORT` for the TLS port. If they speak plaintext --
services, or your own node through a delegation tunnel -- the default is the
right one.

TLS on the target does not change who the node thinks is calling. See
[Identity](#identity).

## Two deployments

**Expose each of our peers** (the case this was written for). Launch one
instance on each peer, target unset. The instance's slot is that peer's
gateway. Anyone who can reach the instance -- because the peer published the
slot, or because our node tunnelled it back (`DELEGATION_TUNNEL_POLICY`) --
speaks Gateway to that peer. We already had a connection to them (that is how
we launched the service). This is how *others* get one.

**Expose us through our peers.** Launch one instance on each reachable peer,
`TARGET` set to our gateway. Anyone who can reach that peer can reach us. The
peer must be able to dial us. If we are behind NAT, this direction does not
work without a reverse connection. This service does not open one.

## Identity

This process does not read gRPC method names. It forwards every byte.

The node identifies a local instance by the source IP of the gateway TCP
connection. The splice opens that connection from this instance. For RPCs
that use `require_caller`, that check returns this instance and does not
require a `Client`. That skip is the source IP only. It is not a rewrite
of the request.

That means:

- Client-auth RPCs (`StartService`, `GetPeerInfo`, `ResolveNetwork`,
  `IntroducePeer`, `AssociateClient`, `GenerateDepositToken`, `Payable`,
  `GetServiceEstimatedCost`, `GetResourceAvailability`, `GetService`)
  skip the Client check because of this instance IP.
- `StartService` with **no** `Client` in the envelope: this instance is
  the parent. RecursionGuard is off. Each start is a new tree. Child cost
  comes from this instance's balance.
- `StartService` **with** a `Client` in the envelope: RecursionGuard is
  on. That `client_id` is the parent and is billed. The IP skip still
  applies, so a missing or unknown Client is not required for auth.
- `ModifyServiceSystemResources` changes **this** instance (local-address).
- `GetPeerInfo` returns the node's public announcement: public key, URIs,
  payment contracts, reputation proofs. It does not return a mnemonic or a
  private key. This process does not read host keys.
- Token RPCs (`StopService`, `ModifyDeposit`, `GetMetrics`, `ServiceTunnel`,
  `Observe`) still need the instance token in the message.
- `Chat` is not local-instance-exempt. It still needs `ChatMessage.client_id`
  bound to a peer.
- `GenerateClient` has no auth.

The slot is a full `celaut.Gateway`. Current RPCs: `StartService`,
`StopService`, `ModifyDeposit`, `GetPeerInfo`, `ResolveNetwork`,
`IntroducePeer`, `GenerateClient`, `AssociateClient`, `GenerateDepositToken`,
`Payable`, `ModifyServiceSystemResources`, `GetServiceEstimatedCost`,
`GetResourceAvailability`, `GetService`, `GetMetrics`, `ServiceTunnel`,
`Observe`, `Chat`.

Anyone who can connect to this slot has that identity on the Client-auth
RPCs. Do not publish the slot unless that is what you want. Use
`nodo tunnel` when only the parent host must reach it.

## Network

The spec asks for `*` egress. Local-gateway mode only needs the host gateway,
which nodo always allows. Open egress is for the `TARGET=` case, where the
other end is a different node for every operator and cannot be enumerated in
the spec.

## Pack

```bash
nodo pack .
```

`service.json` is `linux/amd64`. Change `architecture` to match the packer
(`linux/arm64` on an Asahi/ARM host).

The Dockerfile copies with `COPY ./service /service`. The leading `./` is
required. The packer rewrites that source into the `.service/service/` tree.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

No protobuf library on either side: `tests/wire.py` encodes the same fields
`service/config.py` decodes. If a fixture written there cannot be read here,
the decoder is wrong. `tests/test_protoc.py` also decodes a `protoc --encode`
fixture of `celaut.ConfigurationFile`.
