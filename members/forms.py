from django import forms

from .models import Member


class InscriptionForm(forms.ModelForm):

    choice_inscription = [
        ('Tarif réduit', 'Tarif réduit'),
        ('Tarif plein', 'Tarif plein'),
        ('Tarif pro', 'Tarif pro'),
        ('Tarif mécène', 'Tarif mécène')
    ]

    class Meta:
        model = Member
        fields = ('civility', 'name', 'surname', 'address', 'locality', 'npa', 'mail', 'phone_number')

    Choix_tarif = forms.ChoiceField(choices=choice_inscription)
