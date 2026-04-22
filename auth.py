from passlib.context import CryptContext

# Configuramos el esquema de cifrado
# Usamos 'argon2', que es el ganador del Password Hashing Competition
# y es extremadamente resistente a ataques de fuerza bruta.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Recibe una contraseña en texto plano y la convierte en un hash
    indescifrable para guardar en la base de datos.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compara la contraseña que ingresa el médico en el login con el 
    hash guardado en la base de datos.
    """
    return pwd_context.verify(plain_password, hashed_password)