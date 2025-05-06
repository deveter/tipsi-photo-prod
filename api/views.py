import os
import tempfile
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
from api.email import enviar_email_brevo
import logging
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from django.core.mail import EmailMessage
from django.views.generic import View
from django.http import HttpResponse, Http404
from django.conf import settings
import base64

logger = logging.getLogger(__name__)
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
print("🔐 OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY")[:5])

@method_decorator(csrf_exempt, name='dispatch')
class TranscribeView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        image_files = request.FILES.getlist('images')
        if not image_files:
            return Response({"error": "No se recibieron imágenes"}, status=400)

        try:
            image_messages = []
            for image in image_files:
                encoded = base64.b64encode(image.read()).decode("utf-8")
                image_messages.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image.content_type};base64,{encoded}"
                    }
                })

            prompt = """
Analiza las siguientes imágenes de una carta de restaurante y devuelve un JSON con los siguientes campos:

- familia: categoría o sección del producto.
- producto: nombre del producto.
- precio: solo el número, sin símbolo €.
- formato: si aparece una palabra como 'tapa', 'ración', 'plato', etc., inclúyela. Si no, pon "Único".

Ejemplo:
[
  {
    "familia": "Entrantes",
    "producto": "Tortilla de patatas",
    "precio": 3.5,
    "formato": "tapa"
  },
  ...
]

"""
            print("✅ Antes de llamar a OpenAI")
            gpt_response = client.chat.completions.create(
    model="gpt-4-turbo",
    messages=[
    {"role": "system", "content": "Eres un asistente que interpreta cartas..."},
    {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            *image_messages
        ]
    }
]
,
    max_tokens=2000,
    temperature=0.2
)



            structured = gpt_response.choices[0].message.content

            return Response({
                "structured": structured
            })

        except Exception as e:
            logger.exception("❌ Error al procesar imágenes:")
            return Response({"error": str(e)}, status=500)
        
class EnviarCartaView(APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        nombre = request.data.get("nombre_restaurante")
        email = request.data.get("email")
        carta = request.data.get("carta")

        if not nombre or not email or not carta:
            return Response({"error": "Faltan datos"}, status=400)

        try:
            df = pd.DataFrame(carta)
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                excel_path = tmp.name
                df.to_excel(excel_path, index=False)

            asunto = f"📋 Nueva carta enviada por {nombre}"
            cuerpo = f"El restaurante '{nombre}' con email '{email}' ha enviado su carta adjunta en Excel."

            enviar_email_brevo(
                destinatario="ppinar@tipsitpv.com",
                asunto=asunto,
                cuerpo=cuerpo,
                adjunto=excel_path
            )

            return Response({"message": "Carta enviada correctamente"})

        except Exception as e:
            logger.exception("❌ Error al enviar el email:")
            return Response({"error": str(e)}, status=500)


class FrontendAppView(View):
    def get(self, request):
        index_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                return HttpResponse(f.read())
        else:
            raise Http404("index.html no encontrado en STATIC_ROOT")

