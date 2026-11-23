import consul
c = consul.Consul()
import inspect
print(inspect.signature(c.agent.service.register))