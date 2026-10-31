import java.nio.file.*;
public class CheckedNormalize {
 public static void main(String[] args) throws Exception {
  Path root = Paths.get(args[0]).toAbsolutePath().normalize();
  Path p = root.resolve(args[1]).normalize(); if (!p.startsWith(root)) { System.out.print("BLOCKED"); return; }
  System.out.print(new String(Files.readAllBytes(p), "UTF-8"));
 }
}
