import consul
c = consul.Consul()
print(dir(c.agent.service))