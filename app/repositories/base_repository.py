from typing import Generic, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from app.database.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic Base Repository

    Contains common CRUD operations used by all repositories.
    """

    def __init__(self, db: Session, model: Type[ModelType]):
        self.db = db
        self.model = model

    def get(self, id: int) -> Optional[ModelType]:
        return (
            self.db.query(self.model)
            .filter(self.model.id == id)
            .first()
        )

    def get_all(self) -> list[ModelType]:
        return self.db.query(self.model).all()

    def create(self, **kwargs) -> ModelType:
        obj = self.model(**kwargs)

        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)

        return obj

    def update(self, obj: ModelType, **kwargs) -> ModelType:
        for key, value in kwargs.items():
            setattr(obj, key, value)

        self.db.commit()
        self.db.refresh(obj)

        return obj

    def delete(self, obj: ModelType):
        self.db.delete(obj)
        self.db.commit()