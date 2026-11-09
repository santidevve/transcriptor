import React, { useState } from 'react';
import { StyleSheet, Text, View, TouchableOpacity } from 'react-native';

export default function App() {
  // Manejo de estado básico
  const [contador, setContador] = useState(0);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>¡Mi Primer Frontend!</Text>
      
      <Text style={styles.counterText}>Clics: {contador}</Text>

      {/* TouchableOpacity es el "botón" personalizable por defecto */}
      <TouchableOpacity 
        style={styles.button} 
        onPress={() => setContador(contador + 1)}
      >
        <Text style={styles.buttonText}>Incrementar</Text>
      </TouchableOpacity>
    </View>
  );
}

// Los estilos se manejan con JavaScript mediante un objeto similar a CSS (Flexbox)
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 20,
    color: '#333',
  },
  counterText: {
    fontSize: 18,
    marginBottom: 10,
  },
  button: {
    backgroundColor: '#007AFF',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});

// Handles the transcription request to the backend API with the provided URL.
const response = await fetch(`${API_URL}/api/transcribir/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url }),
});

const data = await response.json();

// Validates that the data is valid and contains the expected transcription result.
if (!response.ok) throw new Error(data.error || 'No se pudo transcribir');

// Updates the state with the transcription result.
setTranscription(data);