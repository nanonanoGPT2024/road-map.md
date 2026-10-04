from __future__ import annotations
import re
from typing import Any, Dict, Tuple, Type, Optional


class ModelRegistry:
    """Registry terpusat untuk menyimpan semua model aktif."""
    _registry: Dict[str, Type[Model]] = {}

    @classmethod
    def register(cls, model_cls: Type[Model]) -> None:
        table_name = model_cls._meta.get("table_name")
        if table_name in cls._registry:
            raise ValueError(f"Tabel '{table_name}' sudah terdaftar oleh {cls._registry[table_name]}.")
        cls._registry[table_name] = model_cls

    @classmethod
    def get_models(cls) -> Dict[str, Type[Model]]:
        return dict(cls._registry)


class Field:
    """Base Descriptor untuk semua Field ORM."""
    def __init__(self, primary_key: bool = False, nullable: bool = False) -> None:
        self.primary_key = primary_key
        self.nullable = nullable
        self.name: str = ""
        self.storage_name: str = ""

    def __set_name__(self, owner: Type[Any], name: str) -> None:
        self.name = name
        self.storage_name = f"__orm_{name}"

    def __get__(self, instance: Optional[Model], owner: Type[Any]) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.storage_name, None)

    def __set__(self, instance: Model, value: Any) -> None:
        if value is None and not self.nullable:
            raise ValueError(f"Field '{self.name}' tidak boleh bernilai None (nullable=False).")
        self.validate(value)
        instance.__dict__[self.storage_name] = value

    def validate(self, value: Any) -> None:
        """Hook method untuk validasi turunan."""
        pass


class StringField(Field):
    def __init__(self, max_length: int = 255, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.max_length = max_length

    def validate(self, value: Any) -> None:
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(f"Field '{self.name}' harus berupa string.")
            if len(value) > self.max_length:
                raise ValueError(f"Panjang string untuk '{self.name}' melebihi batas {self.max_length}.")


class IntegerField(Field):
    def validate(self, value: Any) -> None:
        if value is not None and not isinstance(value, int):
            raise TypeError(f"Field '{self.name}' harus berupa integer.")


class ModelMeta(type):
    """
    Metaclass yang mengabstraksi pembentukan skema Model.
    Memvalidasi integritas Primary Key dan mendaftarkan kelas ke Registry.
    """
    def __new__(
        mcls, 
        name: str, 
        bases: Tuple[Type[Any], ...], 
        namespace: Dict[str, Any], 
        **kwargs: Any
    ) -> ModelMeta:
        # Jangan validasi kelas dasar 'Model' itu sendiri
        if not bases:
            return super().__new__(mcls, name, bases, namespace)

        # 1. Ekstrak dan isolasi semua Field descriptors
        fields: Dict[str, Field] = {}
        primary_keys: list[str] = []

        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                fields[key] = value
                if value.primary_key:
                    primary_keys.append(key)

        # 2. Aturan Invarian: Harus memiliki tepat satu Primary Key
        if len(primary_keys) != 1:
            raise SyntaxError(
                f"Model '{name}' harus memiliki tepat satu Primary Key. "
                f"Ditemukan {len(primary_keys)}: {primary_keys}"
            )

        # 3. Ekstrak atau buat table_name otomatis
        custom_table = namespace.get("__table__")
        if custom_table:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", custom_table):
                raise ValueError(f"Nama tabel '{custom_table}' tidak valid!")
            table_name = custom_table
        else:
            table_name = name.lower() + "s"

        # 4. Tambahkan metadata internal ke kelas
        namespace["_fields"] = fields
        namespace["_meta"] = {
            "table_name": table_name,
            "pk_name": primary_keys[0]
        }

        # 5. Bangun kelas secara nyata
        new_class = super().__new__(mcls, name, bases, namespace)

        # 6. Registrasi otomatis
        ModelRegistry.register(new_class)  # type: ignore[arg-type]

        return new_class


class Model(metaclass=ModelMeta):
    """Base class untuk domain logic entitas."""
    def __init__(self, **kwargs: Any) -> None:
        # Mengisi nilai default dan nilai input
        for field_name, field_obj in self._fields.items():
            if field_name in kwargs:
                setattr(self, field_name, kwargs[field_name])
            else:
                setattr(self, field_name, None)

    def to_dict(self) -> Dict[str, Any]:
        """Serialisasi model menjadi dict secara deterministik."""
        return {
            field_name: getattr(self, field_name)
            for field_name in self._fields
        }

    def __repr__(self) -> str:
        pk_field = self._meta["pk_name"]
        pk_val = getattr(self, pk_field, None)
        return f"<{self.__class__.__name__} {pk_field}={pk_val}>"


# --- Pembuktian Eksekusi Produksi ---

if __name__ == "__main__":
    class User(Model):
        __table__ = "app_users"
        
        id = IntegerField(primary_key=True)
        username = StringField(max_length=50)
        email = StringField(max_length=100)

    # 1. Uji Registrasi Otomatis & Metadata
    print("Models terdaftar:", ModelRegistry.get_models())
    assert "app_users" in ModelRegistry.get_models()

    # 2. Uji Instansiasi Valid
    user = User(id=1, username="admin_sys", email="admin@enterprise.internal")
    print(f"Instansiasi: {user}")
    print("Serialisasi:", user.to_dict())

    # 3. Uji Pelanggaran Aturan Invarian Primary Key
    try:
        class BrokenModel(Model):
            # Error: Tidak ada primary_key
            title = StringField()
    except SyntaxError as err:
        print(f"Tertangkap kegagalan validasi PK (Sesuai Desain): {err}")

    # 4. Uji Pelanggaran Tipe Data via Descriptor
    try:
        user.username = 12345  # Type mismatch
    except TypeError as err:
        print(f"Tertangkap validasi tipe runtime: {err}")

    # 5. Uji Batas Karakter
    try:
        user.username = "a" * 51  # Melebihi max_length=50
    except ValueError as err:
        print(f"Tertangkap validasi panjang string: {err}")
