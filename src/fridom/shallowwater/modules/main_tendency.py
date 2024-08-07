from fridom.framework.modules.module_container import ModuleContainer
from fridom.shallowwater.modules.linear_tendency \
    .linear_tendency import LinearTendency
from fridom.shallowwater.modules.advection \
    .sadourny_advection import SadournyAdvection

class MainTendency(ModuleContainer):
    def __init__(self,
                 name="All Tendency Modules",
                 linear_tendency=LinearTendency(),
                 advection=SadournyAdvection()):
        module_list = [
            linear_tendency,  # Always on element 0
            advection         # Always on element 1
        ]
        super().__init__(name=name, module_list=module_list)
        self.additional_modules = []
        return

    def add(self, module):
        super().add(module)
        self.additional_modules.append(module)
        return

    @property
    def linear_tendency(self):
        return self.module_list[0]
    
    @linear_tendency.setter
    def linear_tendency(self, value):
        self.module_list[0] = value
        return
    
    @property
    def advection(self):
        return self.module_list[1]
    
    @advection.setter
    def advection(self, value):
        self.module_list[1] = value
        return

# remove symbols from the namespace
del ModuleContainer, LinearTendency, SadournyAdvection