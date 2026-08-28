import AsyncStorage from "@react-native-async-storage/async-storage";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useEffect, useState } from "react";
import { StatusBar } from "expo-status-bar";
import BoardScreen from "./src/screens/BoardScreen";
import CrewScreen from "./src/screens/CrewScreen";
import HomeScreen from "./src/screens/HomeScreen";
import LoginScreen from "./src/screens/LoginScreen";

const Stack = createNativeStackNavigator();

export default function App() {
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem("userId").then((id) => {
      setLoggedIn(!!id);
      setReady(true);
    });
  }, []);

  if (!ready) return null;

  return (
    <NavigationContainer>
      <StatusBar style="auto" />
      <Stack.Navigator initialRouteName={loggedIn ? "Home" : "Login"}>
        <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Home" component={HomeScreen} options={{ title: "with-care" }} />
        <Stack.Screen
          name="Crew"
          component={CrewScreen}
          options={({ route }: any) => ({ title: route.params?.name ?? "크루" })}
        />
        <Stack.Screen
          name="Board"
          component={BoardScreen}
          options={({ route }: any) => ({ title: `${route.params?.name ?? ""} 주간 보드` })}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
