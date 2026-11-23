import consul
c = consul.Consul()
print([m for m in dir(c.agent.service) if not m.startswith('_')])