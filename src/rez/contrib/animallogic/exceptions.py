from rez.exceptions import RezError

class AnimalLogicRezError(RezError):
    """Base-class Rez error for Animal Logic specific problems."""
    pass


class RezUnleashError(AnimalLogicRezError):
    """An error in the Unleash subsystem."""
    pass

