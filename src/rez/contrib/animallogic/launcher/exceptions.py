from rez.contrib.animallogic.exceptions import AnimalLogicRezError

class LauncherError(AnimalLogicRezError):
    """An error in the Launcher subsystem."""
    pass


class BakerError(AnimalLogicRezError):
    """An error when baking a preset/toolset."""
    pass


class RezResolverError(AnimalLogicRezError):
    """An error when baking a preset/toolset."""
    pass

