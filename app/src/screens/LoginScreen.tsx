import AsyncStorage from "@react-native-async-storage/async-storage";
import { useState } from "react";
import { Alert, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { api } from "../api";
import { ui } from "../ui";

export default function LoginScreen({ navigation }: any) {
  const [name, setName] = useState("");

  const signup = async () => {
    if (!name.trim()) return;
    try {
      const user = await api.post<{ id: string }>("/users", { name: name.trim() });
      await AsyncStorage.setItem("userId", user.id);
      navigation.reset({ index: 0, routes: [{ name: "Home" }] });
    } catch (e: any) {
      Alert.alert("오류", e.message);
    }
  };

  return (
    <View style={ui.container}>
      <Text style={ui.title}>with-care</Text>
      <Text style={ui.subtitle}>단톡방 옆에 사는 총무</Text>
      <TextInput
        style={styles.input}
        placeholder="이름 (dev 가입)"
        value={name}
        onChangeText={setName}
      />
      <TouchableOpacity style={ui.primaryBtn} onPress={signup}>
        <Text style={ui.primaryBtnText}>시작하기</Text>
      </TouchableOpacity>
      <Text style={ui.hint}>* dev 모드: 본인인증(PASS)은 정식 출시 전 연동</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    padding: 12,
    marginTop: 24,
    width: "100%",
  },
});
