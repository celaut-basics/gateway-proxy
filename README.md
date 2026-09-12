# gateway-proxy

A TCP splice packaged as a [Celaut](https://github.com/celaut-project/nodo) service.
Each accepted connection is a byte pipe to a gateway -- no protocol awareness, so
the same binary fronts plaintext gRPC or TLS.

It exists to **expose a node through a service slot**. `ServiceTunnel` already
reaches a *service* without publishing a port; this reaches a *node*. The
gateway of a peer that does not publish itself (`DISABLE_EXPOSE_OUTSIDE`, NAT)
becomes the declared slot of an instance you launched there, which you can then
hand to others, tunnel through your own node, or advertise as another URI for
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

`nodo execute` passes those names with `-e`:

```bash
# On a peer, expose that peer's own gateway as a service slot.
nodo execute gateway-proxy --remote

# On a peer, front *our* gateway instead.
nodo execute gateway-proxy --remote -e TARGET 203.0.113.10:4040

# Same host, TLS port instead of the plaintext one __config__ names.
nodo execute gateway-proxy --remote -e TARGET_PORT 443
```

`__config__.gateway` is the **plaintext** port (what a service speaks). Other
nodes speak TLS to `GATEWAY_PORT`. If the clients of this instance are peers,
pass `TARGET` / `TARGET_PORT` for the TLS port; if they are services -- or your
own node reaching in through a delegation tunnel -- the default is the right
one.

## Two deployments

**Expose each of our peers** (the case this was written for). Launch one
instance on each peer, target unset. The instance's slot is that peer's
gateway. Anyone who can reach the instance -- because the peer published the
slot, or because our node tunnelled it back (`DELEGATION_TUNNEL_POLICY`) --
speaks Gateway to that peer. We already had a connection to them (that is how
we launched the service); this is how *others* get one.

**Expose us through our peers.** Launch one instance on each reachable peer,
`TARGET` set to our gateway. Anyone who can reach that peer can reach us. The
peer must be able to dial us; if we are behind NAT, this direction does not
work without a reverse connection, which this service does not open.

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

## Tests

```bash
python3 -m unittest discover -s tests -v
```

No protobuf library on either side: `tests/wire.py` encodes the same fields
`service/config.py` decodes. If a fixture written there cannot be read here,
the decoder is wrong.
