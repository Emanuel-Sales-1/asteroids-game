import pygame, random
from circleshape import CircleShape
from constants import *

class Asteroid(CircleShape):
    def __init__(self, x: float, y: float, radius: float) -> None:
        super().__init__(x, y, radius)

    def split(self) -> None:
        self.kill()
        if self.radius <= ASTEROID_MIN_RADIUS:
            return
        else:
            angle = random.uniform(20, 50)
            new_radius = self.radius - ASTEROID_MIN_RADIUS
            first_asteroid = Asteroid(self.position, self.position, new_radius)
            first_asteroid.velocity = self.velocity.rotate(angle) * 1.2
            second_asteroid = Asteroid(self.position, self.position, new_radius)
            second_asteroid.velocity = self.velocity.rotate(-angle) * 1.2
    def draw(self, screen: pygame.Surface) -> None:
        color: str = "White"
        pygame.draw.circle(screen, color, self.position, self.radius, LINE_WIDTH)

    def update(self, dt: float) -> None:
        self.position += self.velocity * dt